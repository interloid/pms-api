from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Product Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str

    SESSION_EXPIRE_DAYS: int = 7

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    MICROSOFT_CLIENT_ID: str
    MICROSOFT_CLIENT_SECRET: str
    MICROSOFT_REDIRECT_URI: str
    MICROSOFT_TENANT_ID: str

    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    GITHUB_REDIRECT_URI: str

    OAUTH_STATE_EXPIRE_SECONDS: int = 600

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_USERNAME: str
    REDIS_PASSWORD: str | None = None

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str

    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str
    SMTP_FROM_NAME: str = "Product Management System"
    SMTP_USE_TLS: bool = False

    PASSCODE_EXPIRE_SECONDS: int = 300
    PASSCODE_LENGTH: int = 6
    PASSCODE_MAX_ATTEMPTS: int = 3

    CORS_ORIGINS: str = "http://localhost:5173"

    YOUR_REACT_URL: str = "http://localhost:5173/callback"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
