from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from psycopg import connect
from redis import Redis

from app.config import settings


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


def check_openclaw() -> bool:
    request = Request(f"{settings.openclaw_gateway_url}/healthz")
    if settings.openclaw_gateway_token:
        request.add_header("Authorization", f"Bearer {settings.openclaw_gateway_token}")

    try:
        with urlopen(request, timeout=2) as response:
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


def readiness_payload() -> dict[str, Any]:
    return {
        "database_configured": bool(settings.database_url),
        "database_connected": check_postgres(),
        "redis_configured": bool(settings.redis_url),
        "redis_connected": check_redis(),
        "openclaw_configured": bool(settings.openclaw_gateway_url),
        "openclaw_reachable": check_openclaw(),
        "openclaw_token_configured": bool(settings.openclaw_gateway_token),
        "telegram_configured": bool(settings.telegram_bot_token),
    }
