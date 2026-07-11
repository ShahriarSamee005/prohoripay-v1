"""Phase 6 — LLM explanation: Groq-when-available, guard, deterministic fallback.

Every test that exercises the "groq" path monkeypatches the single client seam
(`app.modules.llm.client.generate_text`) so the suite is hermetic and never hits
the network. The cache is cleared before each test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import select

from app.core.models import Alert
from app.modules.llm import client, service
from app.modules.llm.config import BANNED_TERMS

_LANGS = ("en", "bn", "banglish")


@pytest.fixture(autouse=True)
def _clear_cache():
    service.clear_cache()
    yield
    service.clear_cache()


@pytest.fixture()
def alert_id(db_session) -> str:
    a = db_session.exec(select(Alert)).first()
    assert a is not None, "expected seeded alerts"
    return a.id


# --------------------------------------------------------------- groq path (mocked)
def test_explain_forecast_and_alert_all_langs(db_session, alert_id, monkeypatch):
    """Non-empty text for a forecast AND an alert, in en/bn/banglish (groq path)."""
    monkeypatch.setattr(
        client, "generate_text",
        lambda system, user: "The balance is being monitored; please review with the agent. A human should decide.",
    )
    for kind, id_ in (("forecast", "physical_cash"), ("alert", alert_id)):
        for lang in _LANGS:
            r = service.explain(db_session, kind, id_, lang)
            assert r["source"] == "groq"
            assert r["text"].strip()
            assert r["lang"] == lang and r["kind"] == kind and r["id"] == id_


# ------------------------------------------------------------------- fallback paths
def test_fallback_on_groq_outage(db_session, monkeypatch):
    """Groq error/timeout => source=='fallback', text still readable and safe."""
    def _boom(system, user):
        raise client.GroqUnavailable("simulated timeout")
    monkeypatch.setattr(client, "generate_text", _boom)

    for lang in _LANGS:
        r = service.explain(db_session, "forecast", "physical_cash", lang)
        assert r["source"] == "fallback"
        assert len(r["text"]) > 20
        assert not _has_banned(r["text"])


def test_guard_rejects_banned_word(db_session, monkeypatch):
    """LLM output containing a banned term => guard rejects => fallback."""
    monkeypatch.setattr(
        client, "generate_text",
        lambda system, user: "This activity looks like fraud and needs review.",
    )
    r = service.explain(db_session, "forecast", "physical_cash", "en")
    assert r["source"] == "fallback"
    assert not _has_banned(r["text"])


def test_guard_rejects_fabricated_number(db_session, monkeypatch):
    """LLM output with a figure not in the payload => guard rejects => fallback."""
    monkeypatch.setattr(
        client, "generate_text",
        lambda system, user: "The balance may fall to 12,345,678 BDT very soon. Please review.",
    )
    r = service.explain(db_session, "forecast", "physical_cash", "en")
    assert r["source"] == "fallback"


# ------------------------------------------------------------------ determinism
def test_identical_request_is_cached_and_identical(db_session, monkeypatch):
    calls = {"n": 0}

    def _counting(system, user):
        calls["n"] += 1
        return f"Reply number {calls['n']} is here. Please review with the agent."

    monkeypatch.setattr(client, "generate_text", _counting)

    first = service.explain(db_session, "forecast", "physical_cash", "en")
    second = service.explain(db_session, "forecast", "physical_cash", "en")

    assert first["text"] == second["text"]     # identical (served from cache)
    assert calls["n"] == 1                      # generated once, then cached


# ----------------------------------------------------- analytics stays LLM-free
def test_analytics_modules_do_not_import_llm():
    """The forecast and alerts modules must never import the llm module."""
    root = Path(__file__).resolve().parents[1] / "app" / "modules"
    for module in ("forecast", "alerts"):
        for py in (root / module).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            assert "modules.llm" not in text and "import llm" not in text, (
                f"{py} unexpectedly references the llm module"
            )


def test_forecast_and_alerts_endpoints_unchanged(client):
    """/api/forecast and /api/alerts are untouched by Phase 6 (no explanation field)."""
    fc = client.get("/api/forecast").json()
    assert set(fc.keys()) == {"forecasts", "meta"}
    assert all("text" not in f and "explanation" not in f for f in fc["forecasts"])

    al = client.get("/api/alerts").json()
    assert set(al.keys()) == {"alerts", "context", "meta"}
    assert all("text" not in a and "explanation" not in a for a in al["alerts"])


# -------------------------------------------------------------------- safe lang
def test_fallback_is_safe_language_in_all_langs(db_session, alert_id, monkeypatch):
    monkeypatch.setattr(
        client, "generate_text",
        lambda system, user: (_ for _ in ()).throw(client.GroqUnavailable("force fallback")),
    )
    for kind, id_ in (("forecast", "physical_cash"), ("alert", alert_id)):
        for lang in _LANGS:
            r = service.explain(db_session, kind, id_, lang)
            assert r["source"] == "fallback"
            assert not _has_banned(r["text"]), (kind, lang, r["text"])


# ------------------------------------------------------------------------ helper
def _has_banned(text: str) -> bool:
    lowered = text.lower()
    return any(term.strip() in lowered for term in BANNED_TERMS)
