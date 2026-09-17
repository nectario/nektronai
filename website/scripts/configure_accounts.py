"""Provision website account storage and a narrowly scoped runtime secret.

Reads NEKTRON_DB_* from the process environment. No credential values are printed.
Default is a read-only database preflight. Use --apply to provision native accounts.
AWS credentials use the normal SDK chain, or --aws-from-wsl on Windows.
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "accounts"))
import boto3
import pymysql
from botocore.exceptions import ClientError
from store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--aws-from-wsl", action="store_true")
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

    if not args.apply:
        print("Preflight passed. --apply provisions account tables, a scoped DB user, a secret and verified email delivery.")
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

    sender = "info@nektron.ai"
    ses = aws.client("sesv2")
    if not ses.get_email_identity(EmailIdentity=sender).get("VerifiedForSendingStatus"):
        raise RuntimeError("The account email sender is not verified")
    status = ses.get_account()
    if not status.get("SendingEnabled") or not status.get("ProductionAccessEnabled"):
        raise RuntimeError("Production email delivery is not enabled")
    admin.migrate()
    username = "nektron_website_auth"
    password = previous["NEKTRON_DB_PASSWORD"] if previous else secrets.token_urlsafe(48)
    database = settings["NEKTRON_DB_NAME"]
    if not database.replace("_", "").isalnum():
        raise RuntimeError("Unexpected database identifier")
    if previous and (previous["NEKTRON_DB_USER"] != username or previous["NEKTRON_DB_NAME"] != database
                     or previous["NEKTRON_DB_HOST"] != settings["NEKTRON_DB_HOST"]):
        raise RuntimeError("Existing account secret targets differ; manual review required")
    # Preserve prior provider settings for a safe application-version rollback.
    # Native authentication does not use them or change any connector configuration.
    runtime = {**(previous or {}), **settings, "NEKTRON_DB_USER": username, "NEKTRON_DB_PASSWORD": password,
               "NEKTRON_AUTH_EMAIL_FROM": "Nektron <info@nektron.ai>", "NEKTRON_EMAIL_REGION": "us-east-2",
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
        for table in ("WebsiteSession", "WebsiteRateLimit", "WebsiteActionToken"):
            cur.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON `{database}`.`{table}` TO %s@'%%'", (username,))
    Store({**runtime, "NEKTRON_DB_CA_FILE": settings["NEKTRON_DB_CA_FILE"]}).read_session("0" * 64)
    aws.client("iam").put_role_policy(RoleName="aws-elasticbeanstalk-ec2-role",
                                     PolicyName="NektronWebsiteAccounts",
                                     PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": [{
                                         "Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"], "Resource": arn},
                                         {"Effect": "Allow", "Action": ["ses:SendEmail"],
                                          "Resource": f"arn:aws:ses:us-east-2:{account}:identity/info@nektron.ai",
                                          "Condition": {"StringEquals": {"ses:FromAddress": "info@nektron.ai"}}}]}))
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
