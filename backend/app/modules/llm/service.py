"""Explanation orchestration: load authoritative facts -> Groq -> guard -> cache.

The number-bearing object is loaded from OUR data by id (never client-supplied),
translated by Groq under a constrained prompt, then checked by the deterministic
guard. On any Groq failure OR a guard rejection, the template fallback is used.
Results are cached by (kind, id, lang, data-hash) so a repeat request is instant
and identical.
"""

from __future__ import annotations

import hashlib
import json

from sqlmodel import Session

from app.core.models import Alert
from app.modules.alerts.router import _to_out as _alert_to_out
from app.modules.forecast.router import _to_out as _forecast_to_out
from app.modules.forecast.service import compute_forecasts
from app.modules.llm import client, fallback, guard, prompts


class FactsNotFound(Exception):
    """Raised when the requested forecast pool_id / alert id does not exist."""


# Process-wide cache: {(kind, id, lang, data_hash): {"text", "source"}}.
_CACHE: dict[tuple[str, str, str, str], dict] = {}


def clear_cache() -> None:
    """Test/demo helper to reset the explanation cache."""
    _CACHE.clear()


# ------------------------------------------------------------- authoritative facts
def _load_facts(session: Session, kind: str, id: str) -> dict:
    """Load the contract-shaped structured object we will explain (by id)."""
    if kind == "forecast":
        for result in compute_forecasts(session):
            if result.pool_id == id:
                return _forecast_to_out(result).model_dump()
        raise FactsNotFound(f"no forecast for pool_id {id!r}")
    if kind == "alert":
        alert = session.get(Alert, id)
        if alert is None:
            raise FactsNotFound(f"no alert {id!r}")
        return _alert_to_out(alert).model_dump()
    raise FactsNotFound(f"unknown kind {kind!r}")


def _data_hash(facts: dict) -> str:
    blob = json.dumps(facts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- generate
def _generate(kind: str, lang: str, facts: dict) -> dict:
    """Try Groq under constraints + guard; fall back deterministically on failure."""
    try:
        text = client.generate_text(prompts.system_prompt(kind, lang),
                                    prompts.user_prompt(facts))
        ok, _reason = guard.check(text, facts)
        if ok:
            return {"text": text.strip(), "source": "groq"}
    except client.GroqUnavailable:
        pass
    except Exception:  # any unexpected client error -> safe fallback
        pass
    return {"text": fallback.render(kind, lang, facts), "source": "fallback"}


def explain(session: Session, kind: str, id: str, lang: str) -> dict:
    """Return {text, lang, source, kind, id}; cached by (kind, id, lang, data-hash)."""
    facts = _load_facts(session, kind, id)
    key = (kind, id, lang, _data_hash(facts))
    if key not in _CACHE:
        _CACHE[key] = _generate(kind, lang, facts)
    cached = _CACHE[key]
    return {"text": cached["text"], "lang": lang, "source": cached["source"],
            "kind": kind, "id": id}
