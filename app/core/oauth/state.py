import secrets


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(32)
