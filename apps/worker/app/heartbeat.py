from __future__ import annotations

import time

from redis import Redis

from app.config import settings


def mark_worker_heartbeat(redis: Redis) -> None:
    redis.set(
        settings.worker_heartbeat_key,
        str(time.time()),
        ex=settings.worker_heartbeat_ttl_seconds,
    )
