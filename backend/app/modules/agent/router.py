"""Agent module — serves the single primary super agent.

Self-contained: router + response schema. No analytics, so no `meta` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.models import Agent
from app.modules.agent.schemas import AgentOut

router = APIRouter(prefix="/api", tags=["agent"])


@router.get("/agent", response_model=AgentOut)
def get_agent(session: Session = Depends(get_session)) -> AgentOut:
    """Return the primary super agent."""
    agent = session.exec(select(Agent)).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="No agent seeded. Run `python -m app.core.seed`.")
    return AgentOut(id=agent.id, name=agent.name, area=agent.area, providers=agent.providers)
