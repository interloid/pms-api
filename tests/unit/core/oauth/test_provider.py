import pytest

from app.core.oauth.provider import OAuthProvider


def test_oauth_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        OAuthProvider()


def test_oauth_provider_requires_all_abstract_methods():
    class IncompleteProvider(OAuthProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_oauth_provider_can_be_implemented():
    class TestOAuthProvider(OAuthProvider):
        def get_authorization_url(self, state: str) -> str:
            return f"https://example.com/oauth?state={state}"

        async def exchange_code(self, code: str) -> dict[str, str]:
            return {
                "access_token": "test-access-token",
            }

        async def get_user_info(
            self,
            access_token: str,
        ) -> dict[str, str]:
            return {
                "email": "test@example.com",
            }

    provider = TestOAuthProvider()

    assert (
        provider.get_authorization_url(
            state="test-state",
        )
        == "https://example.com/oauth?state=test-state"
    )
