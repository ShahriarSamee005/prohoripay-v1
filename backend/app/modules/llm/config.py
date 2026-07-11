"""Constants for the LLM explanation module.

Banned vocabulary, supported languages, and provider display labels per language.
The compliance list mirrors the project-wide guardrail (never "fraud" /
"suspicious" / "criminal" / blocking language).
"""

from __future__ import annotations

# Supported output languages.
LANGS: tuple[str, ...] = ("en", "bn", "banglish")

# Never allowed in any generated explanation (compliance is scored). Checked
# case-insensitively as substrings; the space in "block " avoids matching
# innocent words like "blockchain". Bangla equivalents are avoided by prompt;
# this deterministic guard is the English-term backstop.
BANNED_TERMS: tuple[str, ...] = (
    "fraud", "suspicious", "criminal", "blocking", "block ",
    "freeze", "frozen", "illegal", "arrest",
)

# Provider / pool display labels per language.
POOL_LABELS: dict[str, dict[str, str]] = {
    "en": {"physical_cash": "physical cash", "bkash": "bKash",
           "nagad": "Nagad", "rocket": "Rocket"},
    "bn": {"physical_cash": "নগদ টাকা", "bkash": "বিকাশ",
           "nagad": "নগদ", "rocket": "রকেট"},
    "banglish": {"physical_cash": "cash", "bkash": "bKash",
                 "nagad": "Nagad", "rocket": "Rocket"},
}


def pool_label(pool_id: str | None, lang: str) -> str:
    if not pool_id:
        return POOL_LABELS.get(lang, POOL_LABELS["en"]).get("physical_cash", "cash")
    return POOL_LABELS.get(lang, POOL_LABELS["en"]).get(pool_id, pool_id)
