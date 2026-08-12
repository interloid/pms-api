from urllib.parse import urlencode

from app.core.settings import settings
from app.core.oauth.config import GOOGLE_CONFIG


def build_google_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_CONFIG.scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }

    return f"{GOOGLE_CONFIG.authorization_url}?{urlencode(params)}"

