"""Cases module — GET/POST endpoints for the coordination lifecycle.

Serves cases + their immutable history, and applies guarded human transitions.
Illegal transitions return HTTP 409 with a safe message; unknown ids return 404.
No endpoint executes a financial action.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.common.meta import make_meta
from app.core.db import get_session
from app.core.enums import Provider
from app.modules.cases.models import Case
from app.modules.cases.schemas import (
    CaseEventOut,
    CaseOut,
    CasesResponse,
    TransitionRequest,
)
from app.modules.cases.service import (
    CaseNotFound,
    IllegalTransition,
    get_case,
    get_cases,
    history_of,
    transition,
)

router = APIRouter(prefix="/api", tags=["cases"])


def _iso_z(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_out(session: Session, case: Case) -> CaseOut:
    events = history_of(session, case.id)
    return CaseOut(
        id=case.id,
        alert_id=case.alert_id,
        type=case.type,
        provider=case.provider,
        owner_role=case.owner_role,
        status=case.status,
        escalation_level=case.escalation_level,
        next_step=case.next_step,
        recommended_action=case.recommended_action,
        opened_ts=_iso_z(case.opened_ts),
        updated_ts=_iso_z(case.updated_ts),
        sla_minutes=case.sla_minutes,
        history=[
            CaseEventOut(stage=e.stage, actor=e.actor, ts=_iso_z(e.ts), detail=e.detail)
            for e in events
        ],
    )


@router.get("/cases", response_model=CasesResponse)
def list_cases(
    status: str | None = Query(default=None),
    provider: Provider | None = Query(default=None),
    session: Session = Depends(get_session),
) -> CasesResponse:
    """Return all cases (newest first), optionally filtered by status/provider."""
    cases = get_cases(session, status=status, provider=provider.value if provider else None)
    return CasesResponse(cases=[_to_out(session, c) for c in cases], meta=make_meta())


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_one_case(case_id: str, session: Session = Depends(get_session)) -> CaseOut:
    case = get_case(session, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return _to_out(session, case)


def _do_transition(
    case_id: str, action: str, body: TransitionRequest, session: Session
) -> CaseOut:
    try:
        case = transition(session, case_id, action, actor=body.actor, note=body.note)
    except CaseNotFound:
        raise HTTPException(status_code=404, detail="Case not found.")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_out(session, case)


@router.post("/cases/{case_id}/ack", response_model=CaseOut)
def ack_case(
    case_id: str, body: TransitionRequest, session: Session = Depends(get_session)
) -> CaseOut:
    return _do_transition(case_id, "ack", body, session)


@router.post("/cases/{case_id}/escalate", response_model=CaseOut)
def escalate_case(
    case_id: str, body: TransitionRequest, session: Session = Depends(get_session)
) -> CaseOut:
    return _do_transition(case_id, "escalate", body, session)


@router.post("/cases/{case_id}/resolve", response_model=CaseOut)
def resolve_case(
    case_id: str, body: TransitionRequest, session: Session = Depends(get_session)
) -> CaseOut:
    return _do_transition(case_id, "resolve", body, session)
