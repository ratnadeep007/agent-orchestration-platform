import logging
import time
from uuid import UUID

from psycopg import connect
from redis import Redis

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent_platform.worker")
MESSAGE_QUEUE = "message_delivery"


def main() -> None:
    redis = Redis.from_url(settings.redis_url)
    logger.info("worker started")

    while True:
        try:
            item = redis.brpop(MESSAGE_QUEUE, timeout=30)
            if item is None:
                logger.info("worker heartbeat")
                continue

            _, raw_message_id = item
            mark_message_delivered(UUID(raw_message_id.decode("utf-8")))
        except Exception:
            logger.exception("worker dependency check failed")

        time.sleep(1)


def mark_message_delivered(message_id: UUID) -> None:
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE messages
                SET delivery_state = 'delivered'
                WHERE id = %s
                """,
                (message_id,),
            )
            cursor.execute(
                """
                INSERT INTO run_logs (run_id, level, message, metadata)
                SELECT run_id, 'info', 'message delivered by worker', jsonb_build_object('message_id', id)
                FROM messages
                WHERE id = %s
                """,
                (message_id,),
            )
        connection.commit()


if __name__ == "__main__":
    main()
