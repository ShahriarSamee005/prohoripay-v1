"""Thin Groq client wrapper — the ONLY place that talks to the LLM.

`generate_text` is the single seam the service calls (and tests monkeypatch). It
raises `GroqUnavailable` on any missing-key / import / API / timeout failure so
the service can fall back deterministically. Nothing here computes analytics.
"""

from __future__ import annotations

from app.core.config import settings


class GroqUnavailable(Exception):
    """Raised when Groq cannot produce a completion (missing key, error, timeout)."""


def generate_text(system: str, user: str) -> str:
    """Return a Groq completion for the given system+user messages.

    Deterministic-leaning (low temperature + fixed seed) so a given input yields
    stable demo text. Raises `GroqUnavailable` on any failure — the caller then
    uses the template fallback.
    """
    if not settings.groq_api_key:
        raise GroqUnavailable("GROQ_API_KEY is not set")

    try:
        from groq import Groq
    except Exception as exc:  # package not installed
        raise GroqUnavailable(f"groq package unavailable: {exc}") from exc

    try:
        client = Groq(
            api_key=settings.groq_api_key,
            timeout=settings.groq_timeout_seconds,
            max_retries=settings.groq_max_retries,
        )
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=320,
            seed=7,
        )
        text = (completion.choices[0].message.content or "").strip()
    except Exception as exc:  # network / API / timeout / shape
        raise GroqUnavailable(f"groq call failed: {exc}") from exc

    if not text:
        raise GroqUnavailable("groq returned empty text")
    return text
