"""Deploy one explicitly reviewed Mail-only candidate; read-only unless --apply.

Uses the configured WSL AWS chain. Does not read account secrets, account rows,
mailboxes or tokens. Public validation never signs in a real user.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import boto3
from botocore.config import Config

REGION = 'us-east-2'
APPLICATION = 'NektronWeb'
ENVIRONMENT = 'nektron-web-si-prod'
EXPECTED_SOURCE = 'nektron-mail-native-20261013-4b684069c55f'
EXPECTED_HASH = '207b277f460ae51c65b600737ff1d940a1b075c2c2f9b7f4314a487384c86d36'
ORIGIN = 'https://nektron.ai'
KEYS = '/api/account/mail-archives/v1/keys'
SYNTHETIC_ID = '11111111-1111-4111-8111-111111111111'
COMBINED = 'mail/archive.read mail/archive.keys'
STABLE_PATHS = (
    '/api/account/health', '/.well-known/oauth-authorization-server',
    '/api/account/oauth/jwks', '/api/account/mail-oauth/jwks',
    '/assets/account.css', '/assets/account.js', '/assets/styles.css', '/assets/atelier.css',
    '/login.html', '/signup.html', '/verify-email.html', '/forgot-password.html',
    '/reset-password.html', '/account.html',
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(path, *, body=None, headers=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = Request(ORIGIN + path, data=data,
                      headers={'User-Agent': 'Nektron-Mail-Release-Check', **({'Content-Type': 'application/json'} if data else {}),
                               **(headers or {})}, method='POST' if data else 'GET')
    try:
        response = build_opener(NoRedirect).open(request, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        content = response.read(2 * 1024 * 1024 + 1)
        if len(content) > 2 * 1024 * 1024:
            raise RuntimeError('Public verification response exceeded bounds')
        return {'status': response.code, 'sha256': hashlib.sha256(content).hexdigest(),
                'cache_control': response.headers.get('Cache-Control'),
                'nosniff': response.headers.get('X-Content-Type-Options'),
                'set_cookie': 'Set-Cookie' in response.headers}


def native(scope):
    return fetch('/api/account/mail-native/session', body={'email': '', 'password': '',
                 'client_id': 'nektron-mail-windows', 'resource': ORIGIN + '/mail',
                 'scope': scope, 'approve': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--resume-version', help='Resume validation/deployment of the exact already uploaded candidate')
    args = parser.parse_args()
    candidate = args.candidate.resolve(strict=True)
    if candidate.suffix != '.zip' or hashlib.sha256(candidate.read_bytes()).hexdigest() != EXPECTED_HASH:
        raise RuntimeError('Candidate does not match the exact reviewed SHA-256')
    report = {'candidate_sha256': EXPECTED_HASH, 'source_version': EXPECTED_SOURCE,
              'deployed': False, 'before': {}, 'after': {}}
    for path in STABLE_PATHS:
        result = fetch(path)
        if result['status'] != 200:
            raise RuntimeError('Public baseline endpoint is not healthy: ' + path)
        report['before'][path] = result
    report['before']['native_read_empty'] = native('mail/archive.read')
    report['before']['native_combined_empty'] = native(COMBINED)
    if report['before']['native_read_empty']['status'] != 401:
        raise RuntimeError('Legacy native baseline rejected the documented request shape')
    (candidate.parent / 'deployment-baseline-permissions-fixed.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    session = boto3.Session(region_name=REGION)
    config = Config(connect_timeout=5, read_timeout=20, retries={'mode': 'standard', 'total_max_attempts': 2})
    eb = session.client('elasticbeanstalk', config=config)
    def environment():
        found = eb.describe_environments(ApplicationName=APPLICATION, EnvironmentNames=[ENVIRONMENT])['Environments']
        if len(found) != 1:
            raise RuntimeError('Exact existing deployment target was not found')
        return found[0]
    current = environment()
    if current['VersionLabel'] != EXPECTED_SOURCE or current['Status'] != 'Ready' or current.get('Health') != 'Green':
        raise RuntimeError('Existing service is not the exact healthy reviewed source version')
    print('Read-only public baseline and exact Ready/Green deployment target verified.', flush=True)
    if not args.apply:
        print('No upload or deployment performed; explicit --apply is required.', flush=True)
        return
    label = args.resume_version or ('nektron-mail-archive-keys-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + EXPECTED_HASH[:12])
    if not re.fullmatch(r'nektron-mail-archive-keys-[0-9]{8}T[0-9]{6}Z-' + EXPECTED_HASH[:12], label):
        raise RuntimeError('Resume label does not identify the reviewed candidate')
    existing = eb.describe_application_versions(ApplicationName=APPLICATION, VersionLabels=[label])['ApplicationVersions']
    if existing and not args.resume_version:
        raise RuntimeError('Deployment version already exists; it will not be overwritten')
    source_version = eb.describe_application_versions(ApplicationName=APPLICATION, VersionLabels=[EXPECTED_SOURCE])['ApplicationVersions']
    if len(source_version) != 1:
        raise RuntimeError('Reviewed source bundle location is unavailable')
    bucket = source_version[0]['SourceBundle']['S3Bucket']
    object_key = 'mail-archive-keys/' + label + '.zip'
    s3 = session.client('s3', config=config)
    if args.resume_version:
        if len(existing) != 1 or existing[0]['SourceBundle'] != {'S3Bucket': bucket, 'S3Key': object_key}:
            raise RuntimeError('Uploaded version is not the reviewed candidate source location')
        uploaded = s3.get_object(Bucket=bucket, Key=object_key)['Body']
        try:
            data = uploaded.read(candidate.stat().st_size + 1)
        finally:
            uploaded.close()
        if len(data) != candidate.stat().st_size or hashlib.sha256(data).hexdigest() != EXPECTED_HASH:
            raise RuntimeError('Uploaded candidate hash differs; it will not be deployed')
        print('Reverified exact previously uploaded candidate; no duplicate upload/version.', flush=True)
    else:
        s3.upload_file(str(candidate), bucket, object_key)
        eb.create_application_version(ApplicationName=APPLICATION, VersionLabel=label,
            SourceBundle={'S3Bucket': bucket, 'S3Key': object_key}, Process=True,
            Description='Reviewed Mail archive key recovery only; preserves existing website and Connector')
        print('Uploaded immutable reviewed candidate and requested application-version validation.', flush=True)
    deadline = time.monotonic() + 600
    while True:
        version = eb.describe_application_versions(ApplicationName=APPLICATION, VersionLabels=[label])['ApplicationVersions'][0]
        state = version.get('Status', 'Unprocessed')
        if state.casefold() == 'processed':
            break
        if state.casefold() == 'failed' or time.monotonic() > deadline:
            raise RuntimeError('Application-version processing failed or timed out; environment was not updated')
        print('Candidate processing: ' + state, flush=True)
        time.sleep(20)
    current = environment()
    if current['VersionLabel'] != EXPECTED_SOURCE or current['Status'] != 'Ready' or current.get('Health') != 'Green':
        raise RuntimeError('Deployment target changed during preparation; it was not updated')
    eb.update_environment(ApplicationName=APPLICATION, EnvironmentName=ENVIRONMENT, VersionLabel=label)
    report['target_version'] = label
    print('Mail-only deployment started: ' + label, flush=True)
    deadline = time.monotonic() + 1200
    while True:
        current = environment()
        state, health = current['Status'], current.get('Health', 'Unknown')
        print('Deployment: ' + state + ' / ' + health, flush=True)
        if current['VersionLabel'] == label and state == 'Ready' and health == 'Green':
            break
        if time.monotonic() > deadline:
            raise RuntimeError('Deployment did not reach Ready/Green; operator review is required')
        time.sleep(30)
    for path in STABLE_PATHS:
        result = fetch(path)
        if result['status'] != 200 or result['sha256'] != report['before'][path]['sha256']:
            raise RuntimeError('Public endpoint changed unexpectedly: ' + path)
        report['after'][path] = result
    checks = {
        'native_read_empty': (native('mail/archive.read'), 401),
        'native_combined_empty': (native(COMBINED), 401),
        'native_invalid_scope': (native(COMBINED + ' mail/send'), 400),
        'keys_missing_bearer_create': (fetch(KEYS, body={'request_id': SYNTHETIC_ID}), 401),
        'keys_missing_bearer_recover': (fetch(KEYS + '/' + SYNTHETIC_ID), 401),
        'keys_forged_bearer_create': (fetch(KEYS, body={'request_id': SYNTHETIC_ID},
                                           headers={'Authorization': 'Bearer invalid.synthetic.token'}), 401),
        'keys_browser_context': (fetch(KEYS, body={'request_id': SYNTHETIC_ID}, headers={'Origin': ORIGIN}), 401),
        'mail_profile_missing_bearer': (fetch('/api/account/mail-oauth/profile'), 401),
        'mail_profile_forged_bearer': (fetch('/api/account/mail-oauth/profile',
                                           headers={'Authorization': 'Bearer invalid.synthetic.token'}), 401),
    }
    for name, (result, expected) in checks.items():
        if (result['status'] != expected or result['cache_control'] != 'no-store'
                or result['nosniff'] != 'nosniff' or result['set_cookie']):
            raise RuntimeError('Post-deployment rejection/privacy check failed: ' + name)
        report['after'][name] = result
    report['deployed'] = True
    report['verified_at_utc'] = datetime.now(timezone.utc).isoformat()
    (candidate.parent / 'deployment-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Ready/Green and all public health, unchanged asset/JWKS and rejection/privacy checks passed.', flush=True)
    print('Live version: ' + label, flush=True)
    print('No real-user login, token issuance, archive registry row or email access was performed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Deployment stopped: ' + (str(error) if type(error) is RuntimeError else type(error).__name__), flush=True)
        raise SystemExit(1)
