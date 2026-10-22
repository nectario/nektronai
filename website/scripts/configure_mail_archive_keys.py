"""Explicit additive Mail recovery activation; run in the configured WSL zsh environment.

Default is read-only. --apply adds only the MailArchiveKeys registry, exact
runtime grants, one dedicated KMS key/policy, and three account-secret settings.
No existing rows, credentials, snapshots, email storage or compute are changed.
Secret values and infrastructure identifiers are never printed.
"""
import argparse
import json
import os
import re
import ssl
import sys
from pathlib import Path

import boto3
import pymysql
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = 'us-east-2'
APP = 'NektronWeb'
ENVIRONMENT = 'nektron-web-si-prod'
ALIAS = 'alias/nektron-mail-local-archive'
POLICY = 'NektronMailArchiveKeyRecovery'
SETTINGS = ('NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED', 'NEKTRON_MAIL_ARCHIVE_KMS_KEY_ARN', 'NEKTRON_MAIL_ARCHIVE_KMS_REGION')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    session = boto3.Session(region_name=REGION)
    client_config = Config(connect_timeout=5, read_timeout=15, retries={'max_attempts': 2})
    eb = session.client('elasticbeanstalk', config=client_config)
    environment = eb.describe_environments(ApplicationName=APP, EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(environment) != 1 or environment[0]['Status'] != 'Ready':
        raise RuntimeError('Expected existing Ready account-service environment was not found')
    options = eb.describe_configuration_settings(ApplicationName=APP, EnvironmentName=ENVIRONMENT)['ConfigurationSettings'][0]['OptionSettings']
    def setting(namespace, name):
        values = [item['Value'] for item in options if item['Namespace'] == namespace and item['OptionName'] == name]
        if len(values) != 1 or not values[0]:
            raise RuntimeError('Required existing service setting is missing: ' + name)
        return values[0]
    secret_arn = setting('aws:elasticbeanstalk:application:environment', 'NEKTRON_ACCOUNT_SECRET_ARN')
    profile_name = setting('aws:autoscaling:launchconfiguration', 'IamInstanceProfile')
    iam = session.client('iam', config=client_config)
    profile = iam.get_instance_profile(InstanceProfileName=profile_name)['InstanceProfile']
    if len(profile['Roles']) != 1:
        raise RuntimeError('Expected exactly one existing runtime role')
    role = profile['Roles'][0]['RoleName']
    sm = session.client('secretsmanager', config=client_config)
    secret = sm.get_secret_value(SecretId=secret_arn)
    runtime = json.loads(secret['SecretString'])
    if runtime.get('NEKTRON_SITE_ORIGIN') != 'https://nektron.ai' or runtime.get('NEKTRON_MAIL_OAUTH_ENABLED') != 'true':
        raise RuntimeError('Existing shared Mail account service is not the reviewed target')
    if any(not runtime.get('NEKTRON_DB_' + name) for name in ('HOST', 'NAME', 'USER', 'PASSWORD')):
        raise RuntimeError('Existing runtime database configuration is incomplete')
    database = runtime['NEKTRON_DB_NAME']
    if not re.fullmatch(r'[A-Za-z0-9_]{1,64}', database):
        raise RuntimeError('Unsupported database identifier')
    admin_host = os.getenv('MYSQL_HOST') or os.getenv('NEKTRON_DB_HOST')
    admin_user = os.getenv('MYSQL_USERNAME') or os.getenv('NEKTRON_DB_USER')
    admin_password = os.getenv('MYSQL_PASSWORD') or os.getenv('NEKTRON_DB_PASSWORD')
    if not all((admin_host, admin_user, admin_password)):
        raise RuntimeError('Missing configured administrative host/user/password environment variables')
    admin_port = int(os.getenv('MYSQL_PORT') or os.getenv('NEKTRON_DB_PORT') or 3306)
    if admin_host != runtime['NEKTRON_DB_HOST'] or admin_port != int(runtime.get('NEKTRON_DB_PORT', 3306)):
        raise RuntimeError('Configured administrative connection does not match the existing account database host')
    ca = Path(__file__).resolve().parents[1] / 'server/accounts/rds-ca.pem'
    tls = ssl.create_default_context(cafile=str(ca))
    def connect(user, password):
        return pymysql.connect(host=admin_host, port=admin_port, user=user, password=password,
            database=database, ssl=tls, charset='utf8mb4', connect_timeout=5, read_timeout=10,
            write_timeout=10, cursorclass=pymysql.cursors.DictCursor, local_infile=False)
    with connect(admin_user, admin_password) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('User','MailArchiveKeys')")
        tables = {row['TABLE_NAME'] for row in cursor.fetchall()}
        if 'User' not in tables:
            raise RuntimeError('Existing shared account User table is required')
        if 'MailArchiveKeys' in tables:
            cursor.execute('SHOW CREATE TABLE MailArchiveKeys')
            ddl = cursor.fetchone()['Create Table']
            for required in ('`ArchiveId` char(36)', '`OwnerSubject` varbinary(1020)', '`RequestId` char(36)',
                             '`KeyVersion` smallint unsigned', '`WrappedKey` varbinary(6144)',
                             '`CreatedAt` bigint unsigned', 'PRIMARY KEY (`ArchiveId`)',
                             'UNIQUE KEY `uq_mail_archive_owner_request` (`OwnerSubject`,`RequestId`)'):
                if required.lower() not in ddl.lower():
                    raise RuntimeError('Existing archive-key registry differs; no schema changes applied')
        print('Verified TLS and existing shared account database metadata; no account or message rows read.')
        if not args.apply:
            print('Read-only preflight passed. Explicit --apply is required for approved activation.')
            return
        if 'MailArchiveKeys' not in tables:
            source = (ca.parent / 'mail_archive_keys_schema.sql').read_text(encoding='utf-8')
            cursor.execute(source)
        cursor.execute(f"GRANT SELECT,INSERT ON `{database}`.`MailArchiveKeys` TO %s@'%%'", (runtime['NEKTRON_DB_USER'],))
        connection.commit()
    with connect(runtime['NEKTRON_DB_USER'], runtime['NEKTRON_DB_PASSWORD']) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT ArchiveId FROM MailArchiveKeys LIMIT 0')
    kms = session.client('kms', config=client_config)
    try:
        key = kms.describe_key(KeyId=ALIAS)['KeyMetadata']
        tags = {item['TagKey']: item['TagValue'] for item in kms.list_resource_tags(KeyId=key['Arn'])['Tags']}
        if tags.get('Product') != 'NektronMail' or tags.get('Purpose') != 'PortableArchiveRecovery':
            raise RuntimeError('Existing key alias is not owned by this feature')
    except ClientError as error:
        if error.response['Error']['Code'] != 'NotFoundException':
            raise
        key = kms.create_key(Description='Nektron Mail portable local archive recovery only', KeyUsage='ENCRYPT_DECRYPT',
            KeySpec='SYMMETRIC_DEFAULT', Tags=[{'TagKey':'Product','TagValue':'NektronMail'},
            {'TagKey':'Purpose','TagValue':'PortableArchiveRecovery'}])['KeyMetadata']
        kms.create_alias(AliasName=ALIAS, TargetKeyId=key['KeyId'])
    if key['KeyState'] != 'Enabled' or key['KeyUsage'] != 'ENCRYPT_DECRYPT' or key['KeySpec'] != 'SYMMETRIC_DEFAULT':
        raise RuntimeError('Recovery key is not an enabled symmetric encryption key')
    policy = {'Version':'2012-10-17', 'Statement':[{'Effect':'Allow', 'Action':['kms:Encrypt','kms:Decrypt'],
        'Resource':key['Arn'], 'Condition':{'StringEquals':{'kms:EncryptionContext:app':'nektron-mail',
        'kms:EncryptionContext:purpose':'local-archive-v1'}}}]}
    try:
        previous = iam.get_role_policy(RoleName=role, PolicyName=POLICY)['PolicyDocument']
        if previous != policy:
            raise RuntimeError('Existing named runtime policy differs; it was not overwritten')
    except ClientError as error:
        if error.response['Error']['Code'] != 'NoSuchEntity':
            raise
        iam.put_role_policy(RoleName=role, PolicyName=POLICY, PolicyDocument=json.dumps(policy))
    # Refresh the secret immediately before the additive update; preserve every unrelated field.
    fresh = sm.get_secret_value(SecretId=secret_arn)
    current = json.loads(fresh['SecretString'])
    if fresh['VersionId'] != secret['VersionId']:
        raise RuntimeError('Account settings changed during activation; retry after review')
    update = {**current, SETTINGS[0]:'true', SETTINGS[1]:key['Arn'], SETTINGS[2]:REGION}
    for name in SETTINGS:
        if name in current and current[name] != update[name]:
            raise RuntimeError('Existing recovery configuration differs; it was not replaced')
    if update != current:
        sm.put_secret_value(SecretId=secret_arn, SecretString=json.dumps(update))
    print('Approved registry, exact runtime grants, dedicated KMS key/policy and additive settings are ready.')
    print('No email/account rows, existing secret fields, passwords, snapshots or compute were changed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print credential-bearing SDK/SQL exception text.
        print('Archive-key activation stopped: ' + (str(error) if type(error) is RuntimeError else type(error).__name__), file=sys.stderr)
        raise SystemExit(1)
