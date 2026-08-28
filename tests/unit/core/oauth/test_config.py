from app.core.oauth.config import (
    GITHUB_CONFIG,
    GOOGLE_CONFIG,
    MICROSOFT_CONFIG,
    OAUTH_PROVIDERS,
    OAuthProviderConfig,
)


def test_oauth_provider_config_is_dataclass():
    config = OAuthProviderConfig(
        authorization_url="https://example.com/authorize",
        token_url="https://example.com/token",
        userinfo_url="https://example.com/userinfo",
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://example.com/callback",
        scopes=("openid", "email"),
    )

    assert config.authorization_url == "https://example.com/authorize"
    assert config.token_url == "https://example.com/token"
    assert config.userinfo_url == "https://example.com/userinfo"
    assert config.client_id == "client-id"
    assert config.client_secret == "client-secret"
    assert config.redirect_uri == "https://example.com/callback"
    assert config.scopes == ("openid", "email")


def test_google_config():
    assert isinstance(GOOGLE_CONFIG, OAuthProviderConfig)

    assert GOOGLE_CONFIG.authorization_url == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )

    assert GOOGLE_CONFIG.token_url == ("https://oauth2.googleapis.com/token")

    assert GOOGLE_CONFIG.userinfo_url == (
        "https://openidconnect.googleapis.com/v1/userinfo"
    )

    assert GOOGLE_CONFIG.scopes == (
        "openid",
        "email",
        "profile",
    )


def test_microsoft_config():
    assert isinstance(MICROSOFT_CONFIG, OAuthProviderConfig)

    assert "login.microsoftonline.com" in (MICROSOFT_CONFIG.authorization_url)

    assert "/oauth2/v2.0/authorize" in (MICROSOFT_CONFIG.authorization_url)

    assert "login.microsoftonline.com" in (MICROSOFT_CONFIG.token_url)

    assert "/oauth2/v2.0/token" in (MICROSOFT_CONFIG.token_url)

    assert MICROSOFT_CONFIG.userinfo_url == (
        "https://graph.microsoft.com/oidc/userinfo"
    )

    assert MICROSOFT_CONFIG.scopes == (
        "openid",
        "profile",
        "email",
    )


def test_github_config():
    assert isinstance(GITHUB_CONFIG, OAuthProviderConfig)

    assert GITHUB_CONFIG.authorization_url == (
        "https://github.com/login/oauth/authorize"
    )

    assert GITHUB_CONFIG.token_url == ("https://github.com/login/oauth/access_token")

    assert GITHUB_CONFIG.userinfo_url == ("https://api.github.com/user")

    assert GITHUB_CONFIG.scopes == (
        "read:user",
        "user:email",
    )


def test_oauth_providers_contains_all_supported_providers():
    assert set(OAUTH_PROVIDERS) == {
        "google",
        "microsoft",
        "github",
    }


def test_oauth_providers_map_to_correct_configs():
    assert OAUTH_PROVIDERS["google"] is GOOGLE_CONFIG
    assert OAUTH_PROVIDERS["microsoft"] is MICROSOFT_CONFIG
    assert OAUTH_PROVIDERS["github"] is GITHUB_CONFIG
