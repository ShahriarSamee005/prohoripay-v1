"""Response schema for the agent module (contract: Agent)."""

from __future__ import annotations

from pydantic import BaseModel


class AgentOut(BaseModel):
    """GET /api/agent -> Agent."""

    id: str
    name: str
    area: str
    providers: list[str]
