from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://app:app@postgres:5432/agent_platform"
    redis_url: str = "redis://redis:6379/0"
    openclaw_gateway_url: str = "http://openclaw-gateway:18789"
    openclaw_gateway_token: str = ""
    telegram_bot_token: str = ""
    telegram_allowed_chat_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
