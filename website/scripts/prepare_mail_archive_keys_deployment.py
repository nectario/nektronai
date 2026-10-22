"""Prepare, never publish, a Mail-only overlay of the current live source bundle.

Run in WSL with configured AWS credentials. No secrets, rows or live service
settings are read. This downloads the active public-site source bundle, checks
the existing runtime files against the local committed baseline, and overlays
only the reviewed Mail recovery runtime files. Unknown live divergence stops.
"""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

import boto3
from botocore.config import Config

REGION = 'us-east-2'
APPLICATION = 'NektronWeb'
ENVIRONMENT = 'nektron-web-si-prod'
RUNTIME = (
    'app.py', 'connector_oauth_store.py', 'mail_native.py', 'mail_oauth.py',
    'mail_archive_keys.py', 'mail_archive_keys_store.py',
)
EXISTING = RUNTIME[:4]
NEW_RUNTIME = frozenset('server/accounts/' + name for name in RUNTIME[4:])


def runtime_entry(name):
    entry = zipfile.ZipInfo(name)
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    return entry


def repair_runtime_permissions(source, target):
    """Mechanical, immutable ZIP fix: preserve all contents and unrelated modes."""
    if target.exists():
        raise RuntimeError('Corrected candidate already exists and will not be overwritten')
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, 'w') as corrected:
        for old in original.infolist():
            entry = copy.copy(old)
            if entry.filename in NEW_RUNTIME:
                entry.create_system = 3
                entry.external_attr = (0o100644 << 16) | (old.external_attr & 0xffff)
            corrected.writestr(entry, original.read(old.filename))
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target) as corrected:
        if original.namelist() != corrected.namelist():
            raise RuntimeError('Candidate entry list changed during permission correction')
        for name in original.namelist():
            if original.read(name) != corrected.read(name):
                raise RuntimeError('Candidate contents changed during permission correction')
            if name not in NEW_RUNTIME and original.getinfo(name).external_attr != corrected.getinfo(name).external_attr:
                raise RuntimeError('Unrelated candidate permissions changed')
            if name in NEW_RUNTIME and corrected.getinfo(name).external_attr >> 16 != 0o100644:
                raise RuntimeError('New runtime file is not readable by the dedicated service user')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-parent', type=Path)
    parser.add_argument('--repair-candidate', type=Path, help='Prepare a new permissions-only artifact from the reviewed first candidate')
    args = parser.parse_args()
    if args.repair_candidate:
        original = args.repair_candidate.resolve(strict=True)
        if digest(original.read_bytes()) != '24987691561ae506c4f5efa49079bc445ac532b85e91db21447920b61aa5dc79':
            raise RuntimeError('Permission repair requires the exact previously reviewed candidate')
        fixed = original.with_name('candidate-source-permissions-fixed.zip')
        repair_runtime_permissions(original, fixed)
        print('Prepared new immutable candidate with new runtime files mode 100644 only.')
        print('All runtime content bytes and unrelated entry modes are unchanged.')
        print('Corrected candidate: ' + str(fixed))
        print('SHA256: ' + digest(fixed.read_bytes()))
        return
    root = Path(__file__).resolve().parents[2]
    source = root / 'website/server/accounts'
    session = boto3.Session(region_name=REGION)
    config = Config(connect_timeout=5, read_timeout=20, retries={'mode': 'standard', 'total_max_attempts': 2})
    eb = session.client('elasticbeanstalk', config=config)
    found = eb.describe_environments(ApplicationName=APPLICATION, EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(found) != 1 or found[0]['Status'] != 'Ready' or found[0].get('Health') != 'Green':
        raise RuntimeError('Expected healthy Ready account service is required')
    version = found[0]['VersionLabel']
    versions = eb.describe_application_versions(ApplicationName=APPLICATION, VersionLabels=[version])['ApplicationVersions']
    if len(versions) != 1:
        raise RuntimeError('Exact current source version was not found')
    stage = Path(tempfile.mkdtemp(prefix='nektron-mail-archive-candidate-', dir=args.stage_parent))
    original_zip, candidate_zip = stage / 'live-source.zip', stage / 'candidate-source.zip'
    bundle = versions[0]['SourceBundle']
    session.client('s3', config=config).download_file(bundle['S3Bucket'], bundle['S3Key'], str(original_zip))
    manifest = {'source_version': version, 'source_sha256': digest(original_zip.read_bytes()),
                'changed': [], 'unchanged_count': 0, 'tests': 'not yet run', 'published': False}
    with zipfile.ZipFile(original_zip) as original:
        entries = original.infolist()
        if len(entries) > 10000 or sum(entry.file_size for entry in entries) > 512 * 1024 * 1024:
            raise RuntimeError('Source bundle exceeds review bounds')
        names = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if (entry.filename in names or name.is_absolute() or '..' in name.parts
                    or '\\' in entry.filename or entry.flag_bits & 1
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise RuntimeError('Source bundle contains an unsafe or duplicate entry')
            names.add(entry.filename)
        preserved = {}
        anchor = b'<link rel="stylesheet" href="/assets/account.css">'
        for name in EXISTING:
            relative = 'server/accounts/' + name
            baseline = subprocess.check_output(['git', '-C', str(root), 'show', 'HEAD:website/' + relative])
            if relative not in names:
                raise RuntimeError('Live runtime differs from committed baseline: ' + relative)
            live = original.read(relative)
            if live != baseline and name == 'mail_oauth.py':
                # Reviewed deployment-only stylesheet cache buster from the live
                # 2026-10-13 bundle. Preserve it, not a stale unversioned href.
                matched = re.search(rb'<link rel="stylesheet" href="/assets/account\.css\?v=[A-Za-z0-9_-]{1,100}">', live)
                if matched and live.count(matched[0]) == 1 and live.replace(matched[0], anchor) == baseline:
                    preserved[relative] = matched[0]
                else:
                    raise RuntimeError('Live runtime differs from committed baseline: ' + relative)
            elif live != baseline:
                raise RuntimeError('Live runtime differs from committed baseline: ' + relative)
        replacements = {'server/accounts/' + name: (source / name).read_bytes() for name in RUNTIME}
        for relative, reference in preserved.items():
            if replacements[relative].count(anchor) != 1:
                raise RuntimeError('Reviewed stylesheet reference changed in candidate')
            replacements[relative] = replacements[relative].replace(anchor, reference)
        manifest['preserved_live_asset_references'] = sorted(preserved)
        with zipfile.ZipFile(candidate_zip, 'w', compression=zipfile.ZIP_DEFLATED) as candidate:
            for entry in entries:
                before = original.read(entry.filename)
                after = replacements.pop(entry.filename, before)
                candidate.writestr(entry, after)
                if before != after:
                    manifest['changed'].append({'path': entry.filename, 'before': digest(before), 'after': digest(after)})
                else:
                    manifest['unchanged_count'] += 1
            for name, data in replacements.items():
                candidate.writestr(runtime_entry(name), data)
                manifest['changed'].append({'path': name, 'before': None, 'after': digest(data)})
    # Independent content comparison: only allowlisted runtime paths can differ.
    with zipfile.ZipFile(original_zip) as old, zipfile.ZipFile(candidate_zip) as new:
        altered = {name for name in set(old.namelist()) | set(new.namelist())
                   if name not in old.namelist() or name not in new.namelist() or old.read(name) != new.read(name)}
        if not altered.issubset({'server/accounts/' + name for name in RUNTIME}):
            raise RuntimeError('Candidate changed unrelated content')
        new.extractall(stage / 'website')
    # Synthetic tests are added only to the review staging tree, not the bundle.
    tests = stage / 'website/server/accounts/tests'
    tests.mkdir(parents=True, exist_ok=True)
    for test in (source / 'tests').glob('*.py'):
        (tests / test.name).write_bytes(test.read_bytes())
    manifest['candidate_sha256'] = digest(candidate_zip.read_bytes())
    (stage / 'review-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Prepared Mail-only candidate; unrelated source entries preserved: ' + str(manifest['unchanged_count']))
    print('Changed paths: ' + ', '.join(entry['path'] for entry in manifest['changed']))
    print('Candidate review directory: ' + str(stage))
    print('No S3 upload, application version creation or deployment was performed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Candidate preparation stopped: ' + (str(error) if type(error) is RuntimeError else type(error).__name__))
        raise SystemExit(1)
