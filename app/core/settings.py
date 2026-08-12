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
    
    OAUTH_STATE_EXPIRE_SECONDS: int = 600
    
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    
    CORS_ORIGINS: str = "http://localhost:5173"
    
    YOUR_REACT_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
