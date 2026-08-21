from unittest.mock import patch

import pytest

from app.core.oauth.client import get_oauth_client


@patch("app.core.oauth.client.AsyncOAuth2Client")
def test_get_oauth_client_google(mock_client):
    get_oauth_client("google")

    mock_client.assert_called_once_with(
        client_id=mock_client.call_args.kwargs["client_id"],
        client_secret=mock_client.call_args.kwargs["client_secret"],
        scope="openid email profile",
    )


@patch("app.core.oauth.client.AsyncOAuth2Client")
def test_get_oauth_client_microsoft(mock_client):
    get_oauth_client("microsoft")

    assert mock_client.call_args.kwargs["scope"] == ("openid profile email")


@patch("app.core.oauth.client.AsyncOAuth2Client")
def test_get_oauth_client_github(mock_client):
    get_oauth_client("github")

    assert mock_client.call_args.kwargs["scope"] == ("read:user user:email")


def test_get_oauth_client_raises_for_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported OAuth provider: facebook"):
        get_oauth_client("facebook")
