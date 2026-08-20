from urllib.parse import parse_qs, urlparse

from app.core.oauth.state import generate_oauth_state
from app.core.oauth.url import build_google_authorization_url
from app.core.oauth.config import GOOGLE_CONFIG
from app.core.settings import settings


def test_generate_oauth_state_returns_secure_random_state():
    state = generate_oauth_state()

    assert isinstance(state, str)
    assert len(state) > 0


def test_generate_oauth_state_returns_different_values():
    state1 = generate_oauth_state()
    state2 = generate_oauth_state()

    assert state1 != state2


def test_build_google_authorization_url():
    state = "test-oauth-state"

    url = build_google_authorization_url(state)

    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)

    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "accounts.google.com"
    assert parsed_url.path == "/o/oauth2/v2/auth"

    assert params["client_id"][0] == settings.GOOGLE_CLIENT_ID
    assert params["redirect_uri"][0] == settings.GOOGLE_REDIRECT_URI
    assert params["response_type"][0] == "code"
    assert params["scope"][0] == " ".join(GOOGLE_CONFIG.scopes)
    assert params["state"][0] == state
    assert params["access_type"][0] == "offline"
    assert params["prompt"][0] == "select_account"
    
    