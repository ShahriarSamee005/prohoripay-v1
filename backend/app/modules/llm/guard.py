"""Deterministic post-generation safety guard.

Two checks on the LLM's output, independent of the model:
  1. Banned vocabulary — reject any compliance-forbidden term.
  2. Fabricated figures — reject any number in the text that is not backed by a
     value in the source facts (best-effort, tolerant of natural rounding and of
     percent forms of a 0–1 confidence).
Any failure => the service uses the template fallback instead.
"""

from __future__ import annotations

import re

from app.modules.llm.config import BANNED_TERMS

# Numbers like 80,000 or 10.5 or 92 (grouping commas allowed).
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Bengali digits -> ASCII, so bn output is checked the same way.
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def _numbers_in(text: str) -> list[float]:
    ascii_text = text.translate(_BN_DIGITS)
    out: list[float] = []
    for tok in _NUM_RE.findall(ascii_text):
        val = _to_float(tok)
        if val is not None:
            out.append(val)
    return out


def _allowed_numbers(facts: dict) -> list[float]:
    """Every number the model is allowed to echo — pulled from the facts, including
    numbers embedded in evidence strings, plus percent forms of 0–1 values."""
    allowed: set[float] = set()

    def visit(node) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            v = float(node)
            allowed.add(v)
            if 0.0 < v < 1.0:            # confidence 0.83 -> also allow "83(%)"
                allowed.add(round(v * 100, 2))
        elif isinstance(node, str):
            for val in _numbers_in(node):
                allowed.add(val)
        elif isinstance(node, dict):
            for value in node.values():
                visit(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                visit(item)

    visit(facts)
    return sorted(allowed)


def _is_supported(token: float, allowed: list[float]) -> bool:
    # Tolerant of natural rounding ("about 40 minutes" for 37.3): within 10% or 1.
    return any(abs(token - a) <= max(1.0, 0.10 * abs(a)) for a in allowed)


def check(text: str, facts: dict) -> tuple[bool, str]:
    """Return (ok, reason). ok=False means fall back."""
    lowered = text.lower()
    for term in BANNED_TERMS:
        if term in lowered:
            return False, f"banned term: {term.strip()!r}"

    allowed = _allowed_numbers(facts)
    for token in _numbers_in(text):
        if not _is_supported(token, allowed):
            return False, f"unsupported number: {token:g}"
    return True, "ok"
