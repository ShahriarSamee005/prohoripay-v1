"""Alerts module — GET /api/alerts.

Serves persisted anomaly + liquidity alerts (newest first), the context object
(when a known event explains high volume), and the meta envelope.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.common.meta import make_meta
from app.core.db import get_session
from app.core.models import Alert
from app.modules.alerts.schemas import AlertOut, AlertsResponse, Context
from app.modules.alerts.service import ensure_alerts, get_active_context, get_alerts

router = APIRouter(prefix="/api", tags=["alerts"])


def _iso_z(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id, type=a.type, severity=a.severity, label=a.label,
        anomaly_type=a.anomaly_type, provider=a.provider, pool_id=a.pool_id,
        evidence=a.evidence, baseline=a.baseline, observed=a.observed,
        confidence=a.confidence, ts=_iso_z(a.ts), case_id=a.case_id,
    )


@router.get("/alerts", response_model=AlertsResponse)
def list_alerts(session: Session = Depends(get_session)) -> AlertsResponse:
    """Return all alerts (ts desc), context, and meta."""
    ensure_alerts(session)  # lazily populate if empty (e.g. fresh deploy)
    alerts = [_to_out(a) for a in get_alerts(session)]
    ctx = get_active_context(session)
    return AlertsResponse(
        alerts=alerts,
        context=Context(**ctx) if ctx else None,
        meta=make_meta(),
    )
