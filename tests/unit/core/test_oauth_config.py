from pydantic import SecretStr

from app.core.oauth.config import unpack_optional_secret


def test_unpack_optional_secret_returns_none_for_missing_secret():
    assert unpack_optional_secret(None) is None


def test_unpack_optional_secret_returns_secret_value():
    assert unpack_optional_secret(SecretStr("client-secret")) == "client-secret"
