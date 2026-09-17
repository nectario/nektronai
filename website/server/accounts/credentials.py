"""Password handling and account-input validation."""
import hashlib
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from email_validator import EmailNotValidError, validate_email

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, type=Type.ID)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))


def password_valid(value):
    return (isinstance(value, str) and 15 <= len(value) <= 128
            and len(value.encode("utf-8")) <= 512 and bool(value.strip()))


def password_hash(value):
    if not password_valid(value):
        raise ValueError("INVALID_PASSWORD")
    return HASHER.hash(value)


def password_matches(stored, value):
    native = isinstance(stored, str) and stored.startswith("$argon2id$")
    try:
        result = HASHER.verify(stored if native else DUMMY_HASH, value)
        return bool(native and result)
    except (VerificationError, InvalidHashError):
        return False


def credential_tag(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(value):
    if not isinstance(value, str) or len(value) > 320:
        raise ValueError("INVALID_EMAIL")
    try:
        return validate_email(value.strip(), check_deliverability=False,
                              allow_smtputf8=False).normalized.lower()
    except EmailNotValidError:
        raise ValueError("INVALID_EMAIL") from None
