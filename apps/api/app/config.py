from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://app:app@postgres:5432/agent_platform"
    redis_url: str = "redis://redis:6379/0"
    frontend_origin: str = "http://localhost:3000"
    openclaw_gateway_url: str = "http://openclaw-gateway:18789"
    openclaw_public_gateway_url: str = "http://localhost:18789"
    openclaw_gateway_token: str = ""
    openclaw_config_path: str = "/openclaw/config/openclaw.json"
    openclaw_workspace_root: str = "/openclaw/workspace"
    openclaw_container_workspace_root: str = "/home/node/.openclaw/workspace"
    openclaw_container_agent_root: str = "/home/node/.openclaw/agents"
    agent_runtime_provider: str = "openclaw"
    telegram_bot_token: str = ""
    telegram_allowed_chat_id: str = ""
    telegram_webhook_secret: str = ""
    telegram_workflow_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
