"""Provision website account storage and a narrowly scoped runtime secret.

Reads NEKTRON_DB_* from the process environment. No credential values are printed.
Default is a read-only preflight. Use --apply after configuring the Auth0 callback.
AWS credentials use the normal SDK chain, or --aws-from-wsl on Windows.
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "accounts"))
import boto3
import pymysql
from botocore.exceptions import ClientError
from store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--aws-from-wsl", action="store_true")
    parser.add_argument("--client-id", default="9bYdBkEd654k8ktx58UtDqDVL3TnEgJ8")
    parser.add_argument("--issuer", default="https://dev-cmgmokiptmjiwjri.us.auth0.com/")
    args = parser.parse_args()
    settings = {k: v for k, v in os.environ.items() if k.startswith("NEKTRON_DB_")}
    required = ("HOST", "NAME", "USER", "PASSWORD")
    if any(not settings.get("NEKTRON_DB_" + suffix) for suffix in required):
        raise RuntimeError("The NEKTRON database environment is incomplete")
    root = Path(__file__).resolve().parents[1]
    settings["NEKTRON_DB_CA_FILE"] = str(root / "server/accounts/rds-ca.pem")
    admin = Store(settings)
    with admin.connection() as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='User'")
        if cur.fetchone()["total"] != 1:
            raise RuntimeError("The existing User table is required")
    print("Verified TLS database connection and existing User table.")

    query = urlencode({"response_type": "code", "client_id": args.client_id,
                       "redirect_uri": "https://nektron.ai/api/account/callback",
                       "scope": "openid profile email", "state": secrets.token_urlsafe(32),
                       "nonce": secrets.token_urlsafe(32),
                       "code_challenge": secrets.token_urlsafe(32), "code_challenge_method": "S256"})
    try:
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        with opener.open(args.issuer.rstrip("/") + "/authorize?" + query, timeout=15) as response:
            if "/u/" not in response.url:
                raise RuntimeError("Auth0 login redirect needs verification")
    except HTTPError as error:
        message = error.read().decode("utf-8", "replace")
        if "Callback URL mismatch" in message:
            raise RuntimeError("Auth0 rejected the redirect. Add https://nektron.ai/api/account/callback "
                               "to the website client's Allowed Callback URLs.") from None
        raise RuntimeError(f"Auth0 preflight failed with HTTP {error.code}; inspect the provider configuration.") from None
    print("Auth0 callback reaches hosted login.")
    if not args.apply:
        print("Preflight passed. --apply creates two website tables, a scoped DB user, a secret, and its instance-role grant.")
        return

    if args.aws_from_wsl:
        result = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--", "aws", "configure",
                                 "export-credentials", "--format", "process"],
                                check=True, capture_output=True, text=True)
        credential = json.loads(result.stdout)
        aws = boto3.Session(aws_access_key_id=credential["AccessKeyId"],
                            aws_secret_access_key=credential["SecretAccessKey"],
                            aws_session_token=credential.get("SessionToken"), region_name="us-east-2")
    else:
        aws = boto3.Session(region_name="us-east-2")
    account = aws.client("sts").get_caller_identity()["Account"]
    if account != "066738508971":
        raise RuntimeError("Unexpected AWS account")
    sm = aws.client("secretsmanager")
    name = "nektron/website/accounts"
    previous = None
    try:
        existing = sm.get_secret_value(SecretId=name)
        previous = json.loads(existing["SecretString"])
        arn = existing["ARN"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    admin.migrate()
    username = "nektron_website_auth"
    password = previous["NEKTRON_DB_PASSWORD"] if previous else secrets.token_urlsafe(48)
    database = settings["NEKTRON_DB_NAME"]
    if not database.replace("_", "").isalnum():
        raise RuntimeError("Unexpected database identifier")
    if previous and (previous["NEKTRON_DB_USER"] != username or previous["NEKTRON_DB_NAME"] != database
                     or previous["NEKTRON_DB_HOST"] != settings["NEKTRON_DB_HOST"]):
        raise RuntimeError("Existing account secret targets differ; manual review required")
    runtime = {**settings, "NEKTRON_DB_USER": username, "NEKTRON_DB_PASSWORD": password,
               "NEKTRON_AUTH_ISSUER": args.issuer, "NEKTRON_AUTH_CLIENT_ID": args.client_id,
               "NEKTRON_SITE_ORIGIN": "https://nektron.ai", "NEKTRON_ACCOUNT_ENABLED": "true"}
    runtime.pop("NEKTRON_DB_CA_FILE", None)
    if not previous:
        # Keep the generated password recoverable across a partial provisioning attempt.
        arn = sm.create_secret(Name=name, SecretString=json.dumps({**runtime, "NEKTRON_ACCOUNT_ENABLED": "false"}),
                               Description="Nektron website account backend; scoped DB credentials")["ARN"]
    with admin.connection() as c, c.cursor() as cur:
        cur.execute("CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s REQUIRE SSL", (username, password))
    # Prove ownership before granting anything; never replace an existing password.
    authenticated = pymysql.connect(host=settings["NEKTRON_DB_HOST"],
        port=int(settings.get("NEKTRON_DB_PORT", 3306)), user=username, password=password,
        ssl=admin.tls, connect_timeout=5)
    authenticated.close()
    with admin.connection() as c, c.cursor() as cur:
        cur.execute(f"GRANT SELECT,INSERT,UPDATE ON `{database}`.`User` TO %s@'%%'", (username,))
        for table in ("WebsiteSession", "WebsiteRateLimit"):
            cur.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{database}`.`{table}` TO %s@'%%'", (username,))
    Store({**runtime, "NEKTRON_DB_CA_FILE": settings["NEKTRON_DB_CA_FILE"]}).read_session("0" * 64)
    aws.client("iam").put_role_policy(RoleName="aws-elasticbeanstalk-ec2-role",
                                     PolicyName="NektronWebsiteAccounts",
                                     PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [{
                                         "Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"], "Resource": arn}]}))
    print("Account storage and runtime secret are ready.")
    sm.put_secret_value(SecretId=arn, SecretString=json.dumps(runtime))
    print("Set NEKTRON_ACCOUNT_SECRET_ARN for the website deployment to: " + arn)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Avoid accidental DB/credential disclosure in operational logs.
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print("Account configuration failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
