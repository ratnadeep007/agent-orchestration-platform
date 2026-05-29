from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.bus.message import MessageBus, get_message_bus
from app.models.message import Message, MessageCreate, RuntimeEventCreate
from app.repository.message import MessageRepository, get_message_repository
from app.serializers.message import serialize_message

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[Message])
def list_messages(
    repository: MessageRepository = Depends(get_message_repository),
) -> list[Message]:
    return [serialize_message(row) for row in repository.list()]


@router.post("", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def create_message(
    payload: MessageCreate,
    repository: MessageRepository = Depends(get_message_repository),
    bus: MessageBus = Depends(get_message_bus),
) -> Message:
    row = repository.create(payload)
    bus.enqueue(row["id"])
    return serialize_message(row)


@router.post("/runtime-events", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def mirror_runtime_event(
    payload: RuntimeEventCreate,
    repository: MessageRepository = Depends(get_message_repository),
) -> Message:
    return serialize_message(repository.mirror_event(payload))


@router.get("/{message_id}", response_model=Message)
def get_message(
    message_id: UUID,
    repository: MessageRepository = Depends(get_message_repository),
) -> Message:
    row = repository.get(message_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return serialize_message(row)
