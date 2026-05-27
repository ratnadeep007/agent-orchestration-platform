from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents import router as agents_router
from app.config import settings
from app.health import readiness_payload
from app.messages import router as messages_router
from app.workflows import router as workflows_router

app = FastAPI(title="Agent Orchestration API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(agents_router)
app.include_router(messages_router)
app.include_router(workflows_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, object]:
    return readiness_payload()
