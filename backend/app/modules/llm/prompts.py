"""Constrained prompt construction for the explainer.

The system message pins the model to EXPLAIN-ONLY behaviour: use only the provided
facts, invent no numbers, never banned words, advisory + provider-respecting, 2–4
sentences, output strictly in the requested language, end with a human-review note.
The facts object is passed verbatim as JSON — the model translates, never computes.
"""

from __future__ import annotations

import json

_LANG_DIRECTIVE = {
    "en": "Write in clear, simple English.",
    "bn": "Write ONLY in Bengali (Bangla script). Do not use English words or Latin letters.",
    "banglish": ("Write ONLY in Banglish — romanized Bengali written in Latin letters "
                 "(e.g. 'apnar balance kome jacche'). Do NOT use Bengali script and do "
                 "NOT write plain English."),
}

_KIND_FOCUS = {
    "forecast": ("Explain this liquidity forecast for one balance pool: what the balance "
                 "is doing, and what the agent should consider."),
    "alert": ("Explain this activity alert: what was noticed and that it needs a human "
              "review before any decision."),
}


def system_prompt(kind: str, lang: str) -> str:
    """Build the constrained system message."""
    directive = _LANG_DIRECTIVE.get(lang, _LANG_DIRECTIVE["en"])
    focus = _KIND_FOCUS.get(kind, _KIND_FOCUS["forecast"])
    return (
        "You are ProhoriPay's explainer for mobile-money 'super agents'. You translate "
        "an already-computed result into plain language. You are ADVISORY ONLY.\n"
        "STRICT RULES:\n"
        "1. Use ONLY the facts in the JSON provided. Do NOT invent, estimate, or add any "
        "number, amount, time, or percentage that is not in the facts.\n"
        "2. NEVER use the words 'fraud', 'suspicious', 'criminal', or any blocking/freezing "
        "language. Use calm, neutral wording like 'unusual', 'needs review', 'consider'.\n"
        "3. Never claim a final determination and never imply one provider can access or move "
        "another provider's balance. Only the named provider/pool is in scope.\n"
        "4. Keep it to 2–4 short sentences.\n"
        "5. End with a brief note that a human should review/decide.\n"
        f"6. {directive}\n"
        f"TASK: {focus}"
    )


def user_prompt(facts: dict) -> str:
    """The facts payload the model must translate (and nothing more)."""
    return (
        "Explain these facts. Use only what is here; add no other numbers.\n\n"
        f"FACTS (JSON):\n{json.dumps(facts, ensure_ascii=False)}"
    )
