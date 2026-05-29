from uuid import UUID

from redis import Redis

from app.config import settings

MESSAGE_QUEUE = "message_delivery"


class MessageBus:
    def __init__(self, redis: Redis):
        self.redis = redis

    def enqueue(self, message_id: UUID) -> None:
        self.redis.lpush(MESSAGE_QUEUE, str(message_id))


def get_message_bus() -> MessageBus:
    return MessageBus(Redis.from_url(settings.redis_url))
