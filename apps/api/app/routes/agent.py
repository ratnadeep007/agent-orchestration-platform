from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.integrations.runtime import get_runtime_provider
from app.models.agent import Agent, AgentCreate, AgentSyncResult, AgentUpdate
from app.repository.agent import AgentRepository, get_agent_repository
from app.serializers.agent import serialize_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[Agent])
def list_agents(repository: AgentRepository = Depends(get_agent_repository)) -> list[Agent]:
    return [serialize_agent(row) for row in repository.list()]


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    repository: AgentRepository = Depends(get_agent_repository),
) -> Agent:
    return serialize_agent(repository.create(payload))


@router.get("/{agent_id}", response_model=Agent)
def get_agent(
    agent_id: UUID,
    repository: AgentRepository = Depends(get_agent_repository),
) -> Agent:
    row = repository.get(agent_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return serialize_agent(row)


@router.put("/{agent_id}", response_model=Agent)
def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    repository: AgentRepository = Depends(get_agent_repository),
) -> Agent:
    row = repository.update(agent_id, payload)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return serialize_agent(row)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: UUID,
    repository: AgentRepository = Depends(get_agent_repository),
) -> None:
    if not repository.delete(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


@router.post("/{agent_id}/sync-runtime", response_model=AgentSyncResult)
@router.post("/{agent_id}/sync-openclaw", response_model=AgentSyncResult)
def sync_agent(
    agent_id: UUID,
    repository: AgentRepository = Depends(get_agent_repository),
) -> AgentSyncResult:
    row = repository.get(agent_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    runtime = get_runtime_provider()
    result = runtime.sync_agent(row)
    synced = repository.mark_synced(
        agent_id,
        result["openclaw_agent_id"],
        result["openclaw_workspace_path"],
    )
    if not synced:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return AgentSyncResult(
        agent=serialize_agent(synced),
        openclaw_agent_id=result["openclaw_agent_id"],
        openclaw_workspace_path=result["openclaw_workspace_path"],
        local_workspace_path=result["local_workspace_path"],
        files=result["files"],
    )
