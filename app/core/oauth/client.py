from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.core.oauth.config import OAUTH_PROVIDERS


def get_oauth_client(provider: str) -> AsyncOAuth2Client:
    config = OAUTH_PROVIDERS.get(provider)

    if config is None:
        raise ValueError(
            f"Unsupported OAuth provider: {provider}"
        )

    return AsyncOAuth2Client(
        client_id=config.client_id,
        client_secret=config.client_secret,
        scope=" ".join(config.scopes),
    )
    
