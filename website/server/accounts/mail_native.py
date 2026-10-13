"""First-party Mail credential authentication, deliberately not an OAuth grant.

The desktop collects the password for this endpoint. It does not inherit the
system-browser trust boundary, browser SSO, or PKCE security properties.
"""
import json

from authlib.oauth2.rfc6749.errors import InvalidGrantError
from flask import Blueprint, jsonify, request

from credentials import normalize_email, password_matches, password_valid

NATIVE_SESSION_PATH = '/api/account/mail-native/session'
NATIVE_FLOW = 'mail-native-session-v1'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate field')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-JSON constant')


def register_native_session(app, accounts, *, issuer, client_id, resource, scope,
                            login_limited, issue_tokens):
    blueprint = Blueprint('mail_native', __name__)

    @blueprint.post(NATIVE_SESSION_PATH, provide_automatic_options=False)
    def create_session():
        forbidden = {'cookie', 'origin', 'authorization', 'referer', 'content-encoding'}
        if (not request.is_secure or request.host_url.rstrip('/') != issuer
                or request.args or request.mimetype != 'application/json'
                or any(name.lower() in forbidden or name.lower().startswith('sec-fetch-')
                       for name in request.headers.keys())
                or any(name != 'charset' or value.lower() != 'utf-8'
                       for name, value in request.mimetype_params.items())):
            return jsonify(error='INVALID_REQUEST'), 400
        try:
            # Flask's 4096-byte request limit applies before decoding; never cache
            # this password-bearing body as a second parsed request representation.
            data = json.loads(request.get_data(cache=False).decode('utf-8'),
                              object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
            if (not isinstance(data, dict)
                    or set(data) != {'email', 'password', 'client_id', 'resource', 'scope', 'approve'}
                    or data['client_id'] != client_id or data['resource'] != resource
                    or data['scope'] != scope or data['approve'] is not True):
                return jsonify(error='INVALID_REQUEST'), 400
        except (ValueError, UnicodeError, RecursionError):
            return jsonify(error='INVALID_REQUEST'), 400
        try:
            email = normalize_email(data['email'])
            password = data['password']
            if not password_valid(password):
                raise ValueError('Invalid credentials')
        except ValueError:
            return jsonify(error='INVALID_CREDENTIALS'), 401
        # EXACT shared website login budgets: this route cannot double the allowed
        # attempts by using a separate rate-limit namespace.
        if login_limited(email):
            return jsonify(error='TRY_LATER'), 429
        account = accounts.find_account(email)
        matches = password_matches(account['PasswordHash'] if account else None, password)
        if (not account or not matches or account['AccountStatus'] != 'active'
                or account['EmailVerified'] != 1):
            return jsonify(error='INVALID_CREDENTIALS'), 401
        identity = accounts.finish_login(account['UserId'], account['PasswordHash'])
        if not identity:
            return jsonify(error='INVALID_CREDENTIALS'), 401
        try:
            tokens = issue_tokens(identity)
        except InvalidGrantError:
            # An account/password change during issuance must not disclose status
            # or publish a token that has no durably stored refresh family.
            return jsonify(error='INVALID_CREDENTIALS'), 401
        return jsonify(tokens)

    app.register_blueprint(blueprint)
