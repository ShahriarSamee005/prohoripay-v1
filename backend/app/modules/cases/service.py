"""Case lifecycle: auto-create + route from alerts, guarded transitions, audit.

Everything here is advisory. Cases notify, assign, acknowledge, escalate,
recommend, and track — nothing executes, blocks, freezes, transfers, or approves
a financial action. The state machine is guarded (illegal moves raise
`IllegalTransition`, which the router maps to HTTP 409) and the `CaseEvent` trail
is strictly append-only.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.core.models import Alert
from app.modules.cases.config import (
    ALLOWED_TRANSITIONS,
    ROUTING,
    SLA_MINUTES,
    escalated_owner,
)
from app.modules.cases.models import Case, CaseEvent


# --------------------------------------------------------------- domain errors
class CaseNotFound(Exception):
    """Raised when a case id does not exist (router -> HTTP 404)."""


class IllegalTransition(Exception):
    """Raised when a transition is not allowed from the current status (-> 409).

    Message is safe language only (no verdicts, no banned words).
    """


# ----------------------------------------------------- advisory text (safe lang)
def _provider_label(alert: Alert) -> str:
    """Human label for the alert's own pool — never another provider's."""
    if alert.provider:
        return alert.provider
    if alert.pool_id == "physical_cash":
        return "physical cash"
    return alert.pool_id


def build_next_step(alert: Alert) -> str:
    """Advisory next step, provider-respecting and in safe language."""
    if alert.type == "liquidity":
        return f"Review the projected {_provider_label(alert)} shortfall and prepare a top-up"
    pattern = (alert.anomaly_type or "").replace("_", " ").strip() or "flagged"
    return f"Review the {pattern} pattern with the agent"


def build_recommended_action(alert: Alert) -> str:
    """Advisory recommendation — a human decides; nothing is executed."""
    if alert.type == "liquidity":
        return (
            f"Consider adding {_provider_label(alert)} balance via an approved "
            "channel before it runs low"
        )
    return "Review the flagged transactions with the agent before any decision"


# --------------------------------------------------------------- internal audit
def _append_event(
    session: Session, case_id: str, stage: str, actor: str, ts: datetime, detail: str = ""
) -> None:
    """Append one immutable audit entry. Existing entries are never touched."""
    session.add(CaseEvent(case_id=case_id, stage=stage, actor=actor, ts=ts, detail=detail))


def history_of(session: Session, case_id: str) -> list[CaseEvent]:
    """The ordered (append-order) audit trail for a case."""
    return list(
        session.exec(
            select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id)
        ).all()
    )


# --------------------------------------------------------------- auto-creation
def create_case_for_alert(session: Session, alert: Alert, seq: int) -> Case:
    """Create + route ONE case (id `case_{seq:04d}`) from an alert; link the alert.

    The case is stored in status `routed` (raised -> routed), owned per `ROUTING`,
    with two system audit entries appended. Caller commits.
    """
    case_id = f"case_{seq:04d}"
    owner = ROUTING[alert.type]
    case = Case(
        id=case_id,
        alert_id=alert.id,
        type=alert.type,
        provider=alert.provider,
        owner_role=owner,
        status="routed",
        escalation_level=0,
        next_step=build_next_step(alert),
        recommended_action=build_recommended_action(alert),
        opened_ts=alert.ts,
        updated_ts=alert.ts,
        sla_minutes=SLA_MINUTES[alert.type],
    )
    session.add(case)
    _append_event(session, case_id, "raised", "system", alert.ts,
                  f"auto-created from {alert.id}")
    _append_event(session, case_id, "routed", "system", alert.ts,
                  f"routed to {owner}")
    alert.case_id = case_id
    session.add(alert)
    return case


def create_cases_for_alerts(session: Session, alerts: list[Alert]) -> list[Case]:
    """Create + route one case per alert; set each alert's `case_id`.

    Sequential ids `case_0001..` in alert-id order. Used by the full-replace
    `run_detection`; the sim uses `create_case_for_alert` with continuing ids.
    """
    return [
        create_case_for_alert(session, alert, i)
        for i, alert in enumerate(sorted(alerts, key=lambda a: a.id), start=1)
    ]


# --------------------------------------------------------------- state machine
def _apply_escalation(case: Case, now: datetime) -> str:
    """Bump the level and move the owner up the ladder. Returns the new owner."""
    case.escalation_level += 1
    case.owner_role = escalated_owner(case.escalation_level)
    case.status = "escalated"
    case.updated_ts = now
    return case.owner_role


def transition(
    session: Session,
    case_id: str,
    action: str,
    actor: str,
    note: str = "",
    now: datetime | None = None,
) -> Case:
    """Apply a guarded transition, append an actor-attributed audit entry, commit.

    Raises `CaseNotFound` (unknown id) or `IllegalTransition` (disallowed move).
    """
    now = now or datetime.utcnow()
    case = get_case(session, case_id)
    if case is None:
        raise CaseNotFound(f"No case {case_id}.")

    allowed_from, dest = ALLOWED_TRANSITIONS[action]
    if case.status not in allowed_from:
        raise IllegalTransition(
            f"Cannot {action} a case that is '{case.status}'."
        )

    if action == "escalate":
        new_owner = _apply_escalation(case, now)
        detail = note or f"escalated to {new_owner}"
    else:
        case.status = dest
        case.updated_ts = now
        detail = note

    _append_event(session, case.id, dest, actor, now, detail)
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def system_close(session: Session, case: Case, now: datetime, detail: str) -> Case:
    """Auto-resolve a case as a SYSTEM action (e.g. liquidity pressure eased).

    Distinct from the human `resolve` transition: it does not require a prior ack,
    because it records an automatically-detected condition clearing, not a person's
    decision. Still advisory — it only annotates and closes the tracking record.
    Appends a system audit entry; no-op if already resolved.
    """
    if case.status == "resolved":
        return case
    case.status = "resolved"
    case.updated_ts = now
    _append_event(session, case.id, "resolved", "system", now, detail)
    session.add(case)
    return case


def evaluate_escalations(session: Session, now: datetime) -> list[str]:
    """Auto-escalate every open case whose SLA (from `updated_ts`) has elapsed.

    Appends a system audit entry per escalated case. Resolved cases are skipped.
    Wired as a callable now; Phase 5 drives it from the sim clock. Returns the
    ids of the cases escalated.
    """
    escalated: list[str] = []
    for case in session.exec(select(Case)).all():
        if case.status == "resolved":
            continue
        due = case.updated_ts + timedelta(minutes=case.sla_minutes)
        if now > due:
            _apply_escalation(case, now)
            _append_event(session, case.id, "escalated", "system", now,
                          "auto-escalated: SLA exceeded")
            session.add(case)
            escalated.append(case.id)
    session.commit()
    return escalated


# ------------------------------------------------------------------- queries
def get_case(session: Session, case_id: str) -> Case | None:
    return session.get(Case, case_id)


def get_cases(
    session: Session, status: str | None = None, provider: str | None = None
) -> list[Case]:
    """All cases, optionally filtered by status and/or provider, newest first."""
    stmt = select(Case)
    if status is not None:
        stmt = stmt.where(Case.status == status)
    if provider is not None:
        stmt = stmt.where(Case.provider == provider)
    stmt = stmt.order_by(Case.opened_ts.desc(), Case.id.desc())
    return list(session.exec(stmt).all())
