"""LLM module — POST /api/explain.

Explains an authoritative forecast/alert struct in EN/BN/Banglish. Always returns
usable text: Groq under constraints when available, else the template fallback.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.db import get_session
from app.modules.llm.schemas import ExplainRequest, ExplainResponse
from app.modules.llm.service import FactsNotFound, explain

router = APIRouter(prefix="/api", tags=["explain"])


@router.post("/explain", response_model=ExplainResponse)
def post_explain(
    body: ExplainRequest, session: Session = Depends(get_session)
) -> ExplainResponse:
    try:
        result = explain(session, body.kind, body.id, body.lang)
    except FactsNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ExplainResponse(**result)
