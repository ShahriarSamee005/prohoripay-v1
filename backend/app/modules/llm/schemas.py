"""Request/response schemas for POST /api/explain (contract Phase 6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExplainRequest(BaseModel):
    kind: Literal["forecast", "alert"]
    id: str                                   # pool_id (forecast) or alert_id (alert)
    lang: Literal["en", "bn", "banglish"] = "en"


class ExplainResponse(BaseModel):
    text: str
    lang: str
    source: str                               # "groq" | "fallback"
    kind: str
    id: str
