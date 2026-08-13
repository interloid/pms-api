from dataclasses import dataclass

from app.core.settings import settings


@dataclass
class OAuthProviderConfig:
    authorization_url: str
    token_url: str
    userinfo_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...]


GOOGLE_CONFIG = OAuthProviderConfig(
    authorization_url=("https://accounts.google.com/o/oauth2/v2/auth"),
    token_url=("https://oauth2.googleapis.com/token"),
    userinfo_url=("https://openidconnect.googleapis.com/v1/userinfo"),
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    redirect_uri=settings.GOOGLE_REDIRECT_URI,
    scopes=(
        "openid",
        "email",
        "profile",
    ),
)


MICROSOFT_CONFIG = OAuthProviderConfig(
    authorization_url=(
        f"https://login.microsoftonline.com/"
        f"{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
    ),
    token_url=(
        f"https://login.microsoftonline.com/"
        f"{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
    ),
    userinfo_url=("https://graph.microsoft.com/oidc/userinfo"),
    client_id=settings.MICROSOFT_CLIENT_ID,
    client_secret=settings.MICROSOFT_CLIENT_SECRET,
    redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    scopes=(
        "openid",
        "profile",
        "email",
    ),
)

GITHUB_CONFIG = OAuthProviderConfig(
    authorization_url=("https://github.com/login/oauth/authorize"),
    token_url=("https://github.com/login/oauth/access_token"),
    userinfo_url=("https://api.github.com/user"),
    client_id=settings.GITHUB_CLIENT_ID,
    client_secret=settings.GITHUB_CLIENT_SECRET,
    redirect_uri=settings.GITHUB_REDIRECT_URI,
    scopes=(
        "read:user",
        "user:email",
    ),
)


OAUTH_PROVIDERS: dict[str, OAuthProviderConfig] = {
    "google": GOOGLE_CONFIG,
    "microsoft": MICROSOFT_CONFIG,
    "github": GITHUB_CONFIG,
}
