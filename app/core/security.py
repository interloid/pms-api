import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt
from pwdlib import PasswordHash
from pydantic import ValidationError

from app.core.logging import get_logger
from app.core.settings import settings
from app.exceptions.custom import UnauthorizedException
from app.schemas.auth_schema import AccessTokenPayload
from app.utils.helpers import utc_now

_password_hash = PasswordHash.recommended()
logger = get_logger(__name__)


def hash_passcode(code: str) -> str:
    return hmac.new(
        settings.PASSCODE_PEPPER.get_secret_value().encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(code: str) -> str:
    return hmac.new(
        settings.REFRESH_TOKEN_PEPPER.get_secret_value().encode("utf-8"),
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


def create_access_token(data: dict) -> str:

    to_encode = data.copy()
    expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})

    return jwt.encode(
        to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM
    )


def decode_token(token: str) -> dict:
    payload = jwt.decode(
        token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM]
    )
    return payload


def validate_access_token_payload(payload: dict) -> AccessTokenPayload:
    try:
        return AccessTokenPayload.model_validate(payload)

    except ValidationError as exc:
        logger.warning(
            "Access token payload validation failed | errors=%s",
            exc.errors(),
        )
        raise UnauthorizedException(message="Invalid access token")
