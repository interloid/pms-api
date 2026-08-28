import hashlib
import hmac
import secrets

from pwdlib import PasswordHash

from app.core.settings import settings

_password_hash = PasswordHash.recommended()


def hash_passcode(code: str) -> str:
    return hmac.new(
        settings.PASSCODE_PEPPER.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_passcode(plain_passcode: str, hashed_passcode: str) -> bool:
    hashed_input = hash_passcode(plain_passcode)

    return secrets.compare_digest(
        hashed_input,
        hashed_passcode,
    )


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)
