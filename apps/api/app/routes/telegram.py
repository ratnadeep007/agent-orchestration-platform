from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from psycopg import Connection

from app.bus.message import MessageBus, get_message_bus
from app.config import settings
from app.db import get_connection
from app.models.message import Message, RuntimeEventCreate
from app.models.telegram import TelegramSendRequest, TelegramWebhookResponse
from app.models.workflow import WorkflowRunCreate
from app.repository.message import MessageRepository
from app.repository.workflow import (
    WorkflowRepository,
    WorkflowRunBus,
    get_workflow_repository,
    get_workflow_run_bus,
)
from app.serializers.message import serialize_message

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger("agent_platform.api.telegram")


def get_telegram_message_repository(
    connection: Connection = Depends(get_connection),
) -> MessageRepository:
    return MessageRepository(connection)


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    repository: MessageRepository = Depends(get_telegram_message_repository),
    workflow_repository: WorkflowRepository = Depends(get_workflow_repository),
    workflow_bus: WorkflowRunBus = Depends(get_workflow_run_bus),
) -> TelegramWebhookResponse:
    _validate_webhook_secret(x_telegram_bot_api_secret_token)

    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return TelegramWebhookResponse(accepted=False)

    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        return TelegramWebhookResponse(accepted=False)

    chat_id = str(chat["id"])
    _validate_allowed_chat(chat_id)

    text = str(message.get("text") or message.get("caption") or "")
    if not text:
        return TelegramWebhookResponse(accepted=False)

    telegram_command, command_args, command_prefix = _parse_telegram_command(text)

    telegram_message_id = message.get("message_id")
    external_id = (
        f"telegram:{chat_id}:{telegram_message_id}"
        if telegram_message_id is not None
        else f"telegram:{chat_id}:{update.get('update_id', 'unknown')}"
    )
    row = repository.mirror_event(
        RuntimeEventCreate(
            source="telegram",
            event_type="telegram.message.received",
            channel="telegram",
            direction="inbound",
            body=text,
            external_id=external_id,
            metadata={
                "chat_id": chat_id,
                "update_id": update.get("update_id"),
                "message_id": telegram_message_id,
                "from": message.get("from", {}),
            },
        )
    )
    if row.get("run_id"):
        return TelegramWebhookResponse(
            accepted=True,
            message=serialize_message(row),
            workflow_run_id=row["run_id"],
        )
    workflow_run_id = _start_telegram_workflow(
        chat_id=chat_id,
        message=row,
        text=text,
        telegram_command=telegram_command,
        command_args=command_args,
        command_prefix=command_prefix,
        workflow_repository=workflow_repository,
        workflow_bus=workflow_bus,
    )
    if workflow_run_id:
        attached = repository.attach_run(row["id"], workflow_run_id)
        if attached:
            row = attached
    return TelegramWebhookResponse(
        accepted=True,
        message=serialize_message(row),
        workflow_run_id=workflow_run_id,
    )


@router.post("/messages", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def queue_telegram_message(
    payload: TelegramSendRequest,
    repository: MessageRepository = Depends(get_telegram_message_repository),
    bus: MessageBus = Depends(get_message_bus),
) -> Message:
    _validate_allowed_chat(payload.chat_id)
    row = repository.create_outbound(
        channel="telegram",
        body=payload.body,
        metadata={**payload.metadata, "chat_id": payload.chat_id},
    )
    bus.enqueue(row["id"])
    return serialize_message(row)


def _validate_webhook_secret(received_secret: str | None) -> None:
    if settings.telegram_webhook_secret and received_secret != settings.telegram_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram webhook secret",
        )


def _validate_allowed_chat(chat_id: str) -> None:
    if settings.telegram_allowed_chat_id and chat_id != settings.telegram_allowed_chat_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telegram chat is not allowed",
        )


def _start_telegram_workflow(
    *,
    chat_id: str,
    message: dict[str, Any],
    text: str,
    telegram_command: str | None,
    command_args: str,
    command_prefix: bool,
    workflow_repository: WorkflowRepository,
    workflow_bus: WorkflowRunBus,
) -> UUID | None:
    workflow_id = None
    if telegram_command:
        workflow = workflow_repository.get_by_telegram_command(telegram_command)
        if workflow:
            workflow_id = workflow["id"]
        else:
            logger.warning("No workflow mapped to telegram command /%s", telegram_command)
            return None
    elif command_prefix:
        logger.warning("Telegram command prefix did not resolve to a workflow: %s", text)
        return None
    elif settings.telegram_workflow_id:
        try:
            workflow_id = UUID(settings.telegram_workflow_id)
        except ValueError:
            logger.warning("Ignoring invalid TELEGRAM_WORKFLOW_ID: %s", settings.telegram_workflow_id)
            return None
    else:
        return None

    try:
        row = workflow_repository.create_run(
            workflow_id,
            WorkflowRunCreate(
                trigger={
                    "source": "telegram",
                    "chat_id": chat_id,
                    "message_id": str(message["id"]),
                    "text": text,
                    "telegram_command": telegram_command,
                    "command_args": command_args,
                }
            ),
        )
    except Exception:
        logger.exception("Failed to start telegram workflow %s", workflow_id)
        return None

    if not row:
        logger.warning("Ignoring missing TELEGRAM_WORKFLOW_ID workflow: %s", workflow_id)
        return None

    workflow_bus.enqueue(row["id"])
    return row["id"]


def _parse_telegram_command(text: str) -> tuple[str | None, str, bool]:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None, text, False

    first_token, _, remainder = stripped.partition(" ")
    command = first_token[1:]
    if "@" in command:
        command = command.split("@", 1)[0]
    command = command.strip().lower()
    if not command or not all(ch.isalnum() or ch == "_" for ch in command):
        return None, remainder.strip(), True
    return command, remainder.strip(), True
