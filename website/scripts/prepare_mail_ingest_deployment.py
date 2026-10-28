"""Prepare one Mail-ingestion issuer overlay; no deployment or configuration writes.

Run through WSL/zsh's configured AWS chain. The exact healthy current source
bundle is the base, not this checkout's entire website. Only mail_oauth.py can
change; existing public assets, service hooks and permissions remain untouched.
No account secret, signing key, password, token or database row is read.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

REGION = 'us-east-2'
APPLICATION = 'NektronWeb'
ENVIRONMENT = 'nektron-web-si-prod'
RUNTIME = 'server/accounts/mail_oauth.py'
MAX_BYTES = 256 * 1024 * 1024
ASSET = b'<link rel="stylesheet" href="/assets/account.css">'
PATCHES = (
    (b"READ = 'mail/archive.read'\n", b"READ = 'mail/archive.read'\nINGEST = 'mail/archive.ingest'\n"),
    (b"    scopes = frozenset((READ, KEY_SCOPE) if archive_keys_enabled else (READ,))\n",
     b"    # Native database-storage approval creates its own exact-scope family.\n"
     b"    # Browser authorization and existing refresh families never gain this scope.\n"
     b"    ingest_enabled = settings.get('NEKTRON_MAIL_INGEST_ENABLED') == 'true'\n"
     b"    scopes = frozenset(((READ, KEY_SCOPE) if archive_keys_enabled else (READ,))\n"
     b"                       + ((INGEST,) if ingest_enabled else ()))\n"),
    (b"        if kind == 'authorization_code' and (not valid_callback(request.form.get('redirect_uri'))\n",
     b"        if kind == 'authorization_code' and (request.form.get('scope', READ) != READ\n"
     b"                or not valid_callback(request.form.get('redirect_uri'))\n"),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def approved_source(baseline):
    """Apply only the three reviewed regions; unrelated local changes fail closed."""
    result = baseline.replace(b'\r\n', b'\n')
    for before, after in PATCHES:
        if result.count(before) != 1:
            raise RuntimeError('Committed issuer baseline is not the reviewed pre-ingestion source')
        result = result.replace(before, after, 1)
    return result


def prepare_overlay(original_path, candidate_path, *, baseline, local_source):
    if candidate_path.exists():
        raise RuntimeError('Candidate already exists and will not be overwritten')
    wanted = approved_source(baseline)
    if local_source.replace(b'\r\n', b'\n') != wanted:
        raise RuntimeError('Local issuer contains changes beyond the reviewed ingestion scope flag')
    if original_path.stat().st_size > MAX_BYTES:
        raise RuntimeError('Source bundle exceeds review bounds')
    with zipfile.ZipFile(original_path) as original:
        entries = original.infolist()
        if len(entries) > 10000 or sum(entry.file_size for entry in entries) > 512 * 1024 * 1024:
            raise RuntimeError('Source bundle exceeds review bounds')
        seen = set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            if (entry.filename in seen or name.is_absolute() or '..' in name.parts
                    or '\\' in entry.filename or entry.flag_bits & 1
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise RuntimeError('Source bundle contains an unsafe or duplicate entry')
            seen.add(entry.filename)
        if RUNTIME not in seen:
            raise RuntimeError('Current issuer is absent from the source bundle')
        before = original.read(RUNTIME)
        live = before.replace(b'\r\n', b'\n')
        normalized = baseline.replace(b'\r\n', b'\n')
        preserved = None
        if live != normalized:
            reference = re.search(rb'<link rel="stylesheet" href="/assets/account\.css\?v=[A-Za-z0-9_-]{1,100}">', live)
            if not reference or live.count(reference[0]) != 1 or live.replace(reference[0], ASSET) != normalized:
                raise RuntimeError('Live issuer differs from the reviewed committed baseline')
            preserved = reference[0]
            if wanted.count(ASSET) != 1:
                raise RuntimeError('Candidate stylesheet anchor changed')
            wanted = wanted.replace(ASSET, preserved)
        if before.count(b'\r\n') and before.count(b'\n') == before.count(b'\r\n'):
            wanted = wanted.replace(b'\n', b'\r\n')
        with zipfile.ZipFile(candidate_path, 'x') as candidate:
            candidate.comment = original.comment
            for entry in entries:
                candidate.writestr(copy.copy(entry), wanted if entry.filename == RUNTIME else original.read(entry.filename))
    with zipfile.ZipFile(original_path) as original, zipfile.ZipFile(candidate_path) as candidate:
        if original.namelist() != candidate.namelist() or original.comment != candidate.comment:
            raise RuntimeError('Candidate changed unrelated source entries')
        changed = []
        for name in original.namelist():
            a, b = original.getinfo(name), candidate.getinfo(name)
            if (a.external_attr, a.create_system, a.comment, a.extra, a.date_time) != (b.external_attr, b.create_system, b.comment, b.extra, b.date_time):
                raise RuntimeError('Candidate changed source-entry metadata')
            if original.read(name) != candidate.read(name): changed.append(name)
        if changed != [RUNTIME]:
            raise RuntimeError('Candidate must change exactly the reviewed issuer source file')
    return dict(changed=[dict(path=RUNTIME, before=digest(before), after=digest(wanted))],
                unchanged_count=len(entries)-1, preserved_live_stylesheet=preserved is not None,
                source_sha256=digest(original_path.read_bytes()), candidate_sha256=digest(candidate_path.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True, help='Exact reviewed pre-change Git commit/ref')
    parser.add_argument('--stage-parent', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    baseline_commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--verify', args.baseline_ref + '^{commit}'], text=True).strip()
    baseline = subprocess.check_output(['git', '-C', str(root), 'show', baseline_commit + ':website/' + RUNTIME])
    local_source = (root / 'website' / RUNTIME).read_bytes()
    # Validate the candidate before making even a read-only network request.
    if local_source.replace(b'\r\n', b'\n') != approved_source(baseline):
        raise RuntimeError('Local source is outside the reviewed issuer patch')
    import boto3
    from botocore.config import Config
    session = boto3.Session(region_name=REGION)
    config = Config(connect_timeout=5, read_timeout=20, retries={'mode':'standard','total_max_attempts':2})
    eb = session.client('elasticbeanstalk', config=config)
    found = eb.describe_environments(ApplicationName=APPLICATION, EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(found) != 1 or found[0]['Status'] != 'Ready' or found[0].get('Health') != 'Green':
        raise RuntimeError('Expected healthy Ready account service is required')
    current = found[0]; version = current['VersionLabel']
    versions = eb.describe_application_versions(ApplicationName=APPLICATION, VersionLabels=[version])['ApplicationVersions']
    if len(versions) != 1: raise RuntimeError('Exact current source version was not found')
    bundle = versions[0]['SourceBundle']; s3 = session.client('s3', config=config)
    if s3.head_object(Bucket=bundle['S3Bucket'], Key=bundle['S3Key'])['ContentLength'] > MAX_BYTES:
        raise RuntimeError('Source bundle exceeds review bounds')
    stage = Path(tempfile.mkdtemp(prefix='nektron-mail-ingest-candidate-', dir=args.stage_parent))
    original, candidate = stage/'live-source.zip', stage/'candidate-source.zip'
    s3.download_file(bundle['S3Bucket'], bundle['S3Key'], str(original))
    manifest = prepare_overlay(original, candidate, baseline=baseline, local_source=local_source)
    # Fence a source version change while the reviewed source bundle was downloaded.
    again = eb.describe_environments(ApplicationName=APPLICATION, EnvironmentNames=[ENVIRONMENT])['Environments']
    if len(again) != 1 or again[0].get('EnvironmentId') != current.get('EnvironmentId') or again[0]['VersionLabel'] != version or again[0]['Status'] != 'Ready' or again[0].get('Health') != 'Green':
        raise RuntimeError('Live account-service target changed during preparation')
    manifest.update(source_version=version, baseline_commit=baseline_commit, region=REGION,
        target_fingerprint=digest(json.dumps([REGION,APPLICATION,ENVIRONMENT,current.get('EnvironmentId'),version], separators=(',',':')).encode()),
        required_environment_setting={'NEKTRON_MAIL_INGEST_ENABLED':'true'},
        configuration_changed=False, published=False, tests='not yet run against candidate')
    (stage/'review-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Prepared exact one-file issuer candidate; unrelated source and permissions preserved.')
    print('Candidate review directory: ' + str(stage))
    print('Candidate SHA256: ' + manifest['candidate_sha256'])
    print('No configuration, secret, S3 object, application version or environment was changed.')


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('Candidate preparation stopped: ' + (str(error) if type(error) is RuntimeError else type(error).__name__))
        raise SystemExit(1)
