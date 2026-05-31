from typing import Any
from psycopg import connect
from redis import Redis

from app.config import settings
from app.integrations.runtime import get_runtime_provider


def check_postgres() -> bool:
    try:
        with connect(settings.database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except Exception:
        return False


def check_redis() -> bool:
    try:
        return bool(Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping())
    except Exception:
        return False


def readiness_payload() -> dict[str, Any]:
    runtime = get_runtime_provider()
    runtime_reachable = runtime.check_health()
    return {
        "database_configured": bool(settings.database_url),
        "database_connected": check_postgres(),
        "redis_configured": bool(settings.redis_url),
        "redis_connected": check_redis(),
        "runtime_provider": runtime.name,
        "runtime_configured": bool(settings.openclaw_gateway_url),
        "runtime_reachable": runtime_reachable,
        "runtime_token_configured": bool(settings.openclaw_gateway_token),
        "openclaw_configured": bool(settings.openclaw_gateway_url),
        "openclaw_reachable": runtime_reachable,
        "openclaw_token_configured": bool(settings.openclaw_gateway_token),
        "telegram_configured": bool(settings.telegram_bot_token),
    }
