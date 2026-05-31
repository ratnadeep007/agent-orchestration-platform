from __future__ import annotations

from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.integrations.openclaw import sync_agent_to_openclaw


class RuntimeProvider(Protocol):
    name: str

    def check_health(self) -> bool: ...

    def sync_agent(self, agent: dict[str, Any]) -> dict[str, Any]: ...


class OpenClawRuntimeProvider:
    name = "openclaw"

    def check_health(self) -> bool:
        request = Request(f"{settings.openclaw_gateway_url}/healthz")
        if settings.openclaw_gateway_token:
            request.add_header("Authorization", f"Bearer {settings.openclaw_gateway_token}")

        try:
            with urlopen(request, timeout=2) as response:
                return 200 <= response.status < 300
        except (OSError, URLError):
            return False

    def sync_agent(self, agent: dict[str, Any]) -> dict[str, Any]:
        return sync_agent_to_openclaw(agent)


def get_runtime_provider() -> RuntimeProvider:
    provider = settings.agent_runtime_provider.strip().lower()
    if provider in {"", "openclaw"}:
        return OpenClawRuntimeProvider()
    raise RuntimeError(f"Unsupported agent runtime provider: {settings.agent_runtime_provider}")
