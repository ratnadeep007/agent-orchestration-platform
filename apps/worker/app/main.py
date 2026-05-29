import logging
import time
from uuid import UUID

from redis import Redis

from app.config import settings
from app.queues import (
    MESSAGE_QUEUE,
    QUEUE_SOCKET_TIMEOUT_SECONDS,
    QUEUE_WAIT_SECONDS,
    WORKFLOW_RUN_QUEUE,
)
from app.services.message_delivery import mark_message_delivered
from app.services.workflow_execution import execute_workflow_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent_platform.worker")


def main() -> None:
    redis = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=5,
        socket_timeout=QUEUE_SOCKET_TIMEOUT_SECONDS,
    )
    logger.info("worker started")

    while True:
        try:
            item = redis.brpop([WORKFLOW_RUN_QUEUE, MESSAGE_QUEUE], timeout=QUEUE_WAIT_SECONDS)
            if item is None:
                logger.info("worker heartbeat")
                continue

            queue, raw_id = item
            dispatch_job(queue.decode("utf-8"), UUID(raw_id.decode("utf-8")))
        except Exception:
            logger.exception("worker dependency check failed")

        time.sleep(1)


def dispatch_job(queue_name: str, item_id: UUID) -> None:
    if queue_name == WORKFLOW_RUN_QUEUE:
        execute_workflow_run(item_id)
        return

    mark_message_delivered(item_id)


if __name__ == "__main__":
    main()
