"""Guarded one-flag activation for the existing native Mail account service.

Default is read-only. Root/operator must explicitly use --apply. Existing
secret fields stay in memory and are preserved; only the ingestion feature
flag changes. No signing key rotation, database writes or user login occurs.
No secret body is written to files, command lines or output.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import uuid

REGION='us-east-2'
APPLICATION='NektronWeb'
ENVIRONMENT='nektron-web-si-prod'
FLAG='NEKTRON_MAIL_INGEST_ENABLED'
ISSUER_SHA='663320d758a8292d1566d05adc530dc23cd3c004e47f816a893a495d6e899631'


def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise RuntimeError('duplicate_secret_field')
        result[key]=value
    return result


def parse_secret(raw):
    if type(raw) is not str or not 1<=len(raw.encode('utf-8'))<=65536: raise RuntimeError('invalid_secret_document')
    def invalid(_): raise RuntimeError('invalid_secret_document')
    result=json.loads(raw,object_pairs_hook=unique,parse_constant=invalid)
    if type(result) is not dict or result.get('NEKTRON_SITE_ORIGIN')!='https://nektron.ai' or result.get('NEKTRON_MAIL_OAUTH_ENABLED')!='true':
        raise RuntimeError('unexpected_account_service_secret')
    return result


def merge_flag(before):
    if FLAG in before and before[FLAG] not in ('true','false'): raise RuntimeError('unexpected_flag_type')
    after=copy.deepcopy(before); after[FLAG]='true'
    changed=sorted(name for name in set(before)|set(after) if before.get(name)!=after.get(name) or (name in before)!=(name in after))
    if changed not in ([],[FLAG]): raise RuntimeError('unrelated_secret_change')
    if any(after[name]!=value for name,value in before.items() if name!=FLAG): raise RuntimeError('unrelated_secret_change')
    return after,changed


def activate_flag(client,secret_id,*,attempt_id,apply=False,review_prefix='NektronMailIngestReview-'):
    if type(attempt_id) is not str or not re.fullmatch(r'[A-Za-z0-9-]{32,64}',attempt_id): raise RuntimeError('invalid_attempt_id')
    if review_prefix not in ('NektronMailIngestReview-', 'NektronMailRulesReview-'): raise RuntimeError('invalid_review_prefix')
    current=client.get_secret_value(SecretId=secret_id,VersionStage='AWSCURRENT')
    old_id=current.get('VersionId'); before=parse_secret(current.get('SecretString'))
    if type(old_id) is not str or not 32<=len(old_id)<=64 or 'AWSCURRENT' not in current.get('VersionStages',[]): raise RuntimeError('current_version_unverified')
    after,changed=merge_flag(before)
    result=dict(old_version_id=old_id,new_version_id=None,changed_fields=changed,applied=False,
        flag_present=FLAG in before,flag_type=type(before.get(FLAG)).__name__ if FLAG in before else None,
        flag_enabled=before.get(FLAG)=='true',restart_required=bool(changed))
    if not apply or not changed: return result
    serialized=json.dumps(after,separators=(',',':'),ensure_ascii=False)
    if len(serialized.encode('utf-8'))>65536 or parse_secret(serialized)!=after: raise RuntimeError('invalid_merged_secret')
    review=review_prefix+attempt_id
    # VersionStages cannot be empty (API minimum is one label). This unique
    # non-current label prevents PutSecretValue from implicitly moving CURRENT.
    prepared=client.put_secret_value(SecretId=secret_id,ClientRequestToken=attempt_id,
        SecretString=serialized,VersionStages=[review])
    new_id=prepared.get('VersionId')
    if new_id!=attempt_id or 'AWSCURRENT' in prepared.get('VersionStages',[]): raise RuntimeError('prepared_version_unverified')
    again=client.get_secret_value(SecretId=secret_id,VersionStage='AWSCURRENT')
    if again.get('VersionId')!=old_id or parse_secret(again.get('SecretString'))!=before:
        raise RuntimeError('concurrent_secret_change_current_untouched')
    # The service rejects RemoveFromVersionId if CURRENT moved concurrently.
    client.update_secret_version_stage(SecretId=secret_id,VersionStage='AWSCURRENT',MoveToVersionId=new_id,RemoveFromVersionId=old_id)
    published=client.get_secret_value(SecretId=secret_id,VersionStage='AWSCURRENT')
    if published.get('VersionId')!=new_id or parse_secret(published.get('SecretString'))!=after:
        raise RuntimeError('published_version_requires_review')
    client.update_secret_version_stage(SecretId=secret_id,VersionStage=review,RemoveFromVersionId=new_id)
    result.update(new_version_id=new_id,applied=True,flag_enabled=True,restart_required=True)
    return result


def restart_candidate(eb,s3,*,expected_live,label):
    if not re.fullmatch(r'nektron-mail-ingest-restart-[A-Za-z0-9-]{1,65}',label): raise RuntimeError('invalid_restart_label')
    current=eb.describe_environments(ApplicationName=APPLICATION,EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(current)!=1 or current[0]['VersionLabel']!=expected_live or current[0]['Status']!='Ready' or current[0].get('Health')!='Green': raise RuntimeError('restart_target_changed')
    version=eb.describe_application_versions(ApplicationName=APPLICATION,VersionLabels=[expected_live])['ApplicationVersions']
    if len(version)!=1: raise RuntimeError('restart_source_unavailable')
    bundle=version[0]['SourceBundle']; response=s3.get_object(Bucket=bundle['S3Bucket'],Key=bundle['S3Key'])
    body=response['Body']
    try: raw=body.read(256*1024*1024+1)
    finally: body.close()
    if len(raw)>256*1024*1024 or hashlib.sha256(raw).hexdigest()!=ISSUER_SHA: raise RuntimeError('restart_source_hash_mismatch')
    if eb.describe_application_versions(ApplicationName=APPLICATION,VersionLabels=[label])['ApplicationVersions']:
        raise RuntimeError('restart_version_already_exists')
    again=eb.describe_environments(ApplicationName=APPLICATION,EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(again)!=1 or again[0]['VersionLabel']!=expected_live or again[0]['Status']!='Ready' or again[0].get('Health')!='Green': raise RuntimeError('restart_target_changed')
    eb.create_application_version(ApplicationName=APPLICATION,VersionLabel=label,SourceBundle=bundle,Process=True,
        Description='Same reviewed Mail issuer source; restart custom account service after one-flag activation')
    return dict(restart_version_label=label,source_sha256=ISSUER_SHA,environment_updated=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true'); parser.add_argument('--attempt-id',required=True)
    parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--restart-version-label'); parser.add_argument('--expected-live-version')
    args=parser.parse_args()
    report=args.report.resolve()
    if 'private' not in report.parts or report.exists() or not report.parent.is_dir(): raise RuntimeError('new_private_report_required')
    import boto3
    from botocore.config import Config
    session=boto3.Session(region_name=REGION); config=Config(connect_timeout=5,read_timeout=20,retries={'total_max_attempts':2})
    eb=session.client('elasticbeanstalk',config=config)
    environment=eb.describe_environments(ApplicationName=APPLICATION,EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(environment)!=1 or environment[0]['Status']!='Ready' or environment[0].get('Health')!='Green': raise RuntimeError('account_service_not_ready')
    options=eb.describe_configuration_settings(ApplicationName=APPLICATION,EnvironmentName=ENVIRONMENT)['ConfigurationSettings'][0]['OptionSettings']
    arns=[item['Value'] for item in options if item['Namespace']=='aws:elasticbeanstalk:application:environment' and item['OptionName']=='NEKTRON_ACCOUNT_SECRET_ARN']
    if len(arns)!=1: raise RuntimeError('account_secret_unavailable')
    result=activate_flag(session.client('secretsmanager',config=config),arns[0],attempt_id=args.attempt_id,apply=args.apply)
    if args.restart_version_label:
        if not args.apply or not args.expected_live_version or not result['flag_enabled']: raise RuntimeError('explicit_restart_preparation_required')
        result.update(restart_candidate(eb,session.client('s3',config=config),expected_live=args.expected_live_version,label=args.restart_version_label))
    with report.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps(dict(status='flag_activated' if result['applied'] else 'read_only_or_already_enabled',
        changed_fields=result['changed_fields'],flag_present=result['flag_present'],flag_type=result['flag_type'],flag_enabled=result['flag_enabled'],
        restart_required=result['restart_required'],environment_updated=False)))


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps(dict(status='activation_stopped',error_type=type(error).__name__,
            code=str(error) if type(error) is RuntimeError else 'operation_unavailable')))
        raise SystemExit(1)
