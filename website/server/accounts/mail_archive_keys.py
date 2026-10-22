"""Account-assisted local archive key custody, not mailbox access or backup.

Only exact combined-scope Mail sessions may create/recover a key. The backend
owns immutable archive/subject associations; file metadata is never authority.
No mail bytes, password, unwrapped key or bearer token are logged or persisted.
"""
import base64
import hashlib
import json
import re
import secrets
import time
import uuid

import boto3
from botocore.config import Config
from flask import Blueprint, jsonify, request

from mail_archive_keys_store import ArchiveKeyRecord, ArchiveKeyStore

KEY_SCOPE = 'mail/archive.read mail/archive.keys'
KEYS_PREFIX = '/api/account/mail-archives/v1/keys'
KEY_VERSION = 1
_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z', re.ASCII)
_KEY_ARN = re.compile(r'arn:aws:kms:([a-z0-9-]+):[0-9]{12}:key/[a-zA-Z0-9-]{1,80}\Z', re.ASCII)


def canonical_uuid(value):
    return (isinstance(value, str) and bool(_UUID.fullmatch(value))
            and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0)


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError('Duplicate field')
        result[name] = value
    return result


def _invalid_constant(value):
    raise ValueError('Invalid JSON constant')


class KmsArchiveKeys:
    """One configured wrapping key and exact immutable encryption context."""
    def __init__(self, settings, client=None):
        arn = settings.get('NEKTRON_MAIL_ARCHIVE_KMS_KEY_ARN', '')
        region = settings.get('NEKTRON_MAIL_ARCHIVE_KMS_REGION', '')
        matched = _KEY_ARN.fullmatch(arn)
        if not matched or region != matched[1]:
            raise ValueError('Archive KMS key and region must be explicitly configured')
        self.key_arn = arn
        self.client = client or boto3.client('kms', region_name=region, config=Config(
            connect_timeout=3, read_timeout=5, retries={'mode': 'standard', 'total_max_attempts': 2}))

    @staticmethod
    def context(owner, archive_id):
        return {'app': 'nektron-mail', 'purpose': 'local-archive-v1',
                'archive_id': archive_id, 'owner_hash': hashlib.sha256(owner.encode('utf-8')).hexdigest()}

    def wrap(self, owner, archive_id, key):
        result = self.client.encrypt(KeyId=self.key_arn, Plaintext=key,
                                     EncryptionContext=self.context(owner, archive_id), EncryptionAlgorithm='SYMMETRIC_DEFAULT')
        wrapped = result.get('CiphertextBlob')
        if result.get('KeyId') != self.key_arn or not isinstance(wrapped, bytes) or not 1 <= len(wrapped) <= 6144:
            raise ValueError('Archive key wrapping failed')
        return wrapped

    def unwrap(self, record):
        if record.key_version != KEY_VERSION or not 1 <= len(record.wrapped_key) <= 6144:
            raise ValueError('Unsupported archive key')
        result = self.client.decrypt(KeyId=self.key_arn, CiphertextBlob=record.wrapped_key,
            EncryptionContext=self.context(record.owner_subject, record.archive_id), EncryptionAlgorithm='SYMMETRIC_DEFAULT')
        key = result.get('Plaintext')
        if result.get('KeyId') != self.key_arn or not isinstance(key, bytes) or len(key) != 32:
            raise ValueError('Archive key recovery failed')
        return key


def register_archive_keys(app, settings, accounts, *, authenticate, grants, registry=None, keys=None):
    if settings.get('NEKTRON_MAIL_ARCHIVE_KEYS_ENABLED') != 'true':
        return
    registry = registry or ArchiveKeyStore(accounts)
    keys = keys or KmsArchiveKeys(settings)
    blueprint = Blueprint('mail_archive_keys', __name__)

    def error(code, status):
        return jsonify(error=code), status

    def request_identity():
        forbidden = {'cookie', 'origin', 'referer', 'content-encoding'}
        if (not request.is_secure or request.host_url.rstrip('/') != 'https://nektron.ai'
                or request.args or any(name.lower() in forbidden or name.lower().startswith('sec-fetch-')
                                      for name in request.headers.keys())):
            return None
        claims = authenticate(required_scope=KEY_SCOPE)
        if claims is None or not grants.active_mail_archive_grant(claims['grant_id'], claims['sub'], KEY_SCOPE):
            return None
        return claims

    def permitted(claims):
        owner = claims['sub']
        # Check both independent budgets even when the first is exhausted.
        subject_ok = accounts.allow_request('mail-archive-keys:subject:' + owner, limit=60, seconds=600)
        address_ok = accounts.allow_request('mail-archive-keys:ip:' + (request.remote_addr or 'unknown'), limit=120, seconds=600)
        return subject_ok and address_ok

    def release(record, claims):
        if (record.owner_subject != claims['sub'] or not canonical_uuid(record.archive_id)
                or not canonical_uuid(record.request_id)):
            raise ValueError('Invalid archive registry entry')
        key = keys.unwrap(record)
        # Recheck after potentially slow KMS/DB work before returning key bytes.
        if not grants.active_mail_archive_grant(claims['grant_id'], claims['sub'], KEY_SCOPE):
            return error('INVALID_TOKEN', 401)
        return jsonify(archive_id=record.archive_id, owner_subject=record.owner_subject,
                       key_version=KEY_VERSION, data_key=base64.b64encode(key).decode('ascii'))

    @blueprint.post(KEYS_PREFIX, provide_automatic_options=False)
    def create_key():
        try:
            claims = request_identity()
            if claims is None:
                return error('INVALID_TOKEN', 401)
            if (request.mimetype != 'application/json' or
                    any(name != 'charset' or value.lower() != 'utf-8' for name, value in request.mimetype_params.items())):
                return error('INVALID_REQUEST', 400)
            if request.content_length is not None and request.content_length > 256:
                return error('INVALID_REQUEST', 400)
            try:
                raw = request.get_data(cache=False)
                if len(raw) > 256:
                    return error('INVALID_REQUEST', 400)
                body = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
                if not isinstance(body, dict) or set(body) != {'request_id'} or not canonical_uuid(body['request_id']):
                    return error('INVALID_REQUEST', 400)
            except (ValueError, UnicodeError, RecursionError):
                return error('INVALID_REQUEST', 400)
            if not permitted(claims):
                return error('TRY_LATER', 429)
            record = registry.by_request(claims['sub'], body['request_id'])
            if record is None:
                archive_id = str(uuid.uuid4())
                key = secrets.token_bytes(32)
                wrapped = keys.wrap(claims['sub'], archive_id, key)
                record = registry.insert_or_existing(ArchiveKeyRecord(
                    archive_id, claims['sub'], body['request_id'], KEY_VERSION, wrapped, int(time.time())))
            return release(record, claims)
        except Exception:
            # No exception detail: KMS/SQL messages can carry private key material.
            return error('ARCHIVE_KEYS_UNAVAILABLE', 503)

    @blueprint.route(KEYS_PREFIX + '/<archive_id>', methods=['GET'], provide_automatic_options=False)
    def recover_key(archive_id):
        try:
            if request.method != 'GET':
                return error('INVALID_REQUEST', 405)
            claims = request_identity()
            if claims is None:
                return error('INVALID_TOKEN', 401)
            if request.content_length not in (None, 0) or not canonical_uuid(archive_id):
                return error('INVALID_REQUEST', 400)
            if not permitted(claims):
                return error('TRY_LATER', 429)
            record = registry.by_archive(claims['sub'], archive_id)
            if record is None:
                return error('ARCHIVE_NOT_FOUND', 404)
            return release(record, claims)
        except Exception:
            return error('ARCHIVE_KEYS_UNAVAILABLE', 503)

    app.register_blueprint(blueprint)
