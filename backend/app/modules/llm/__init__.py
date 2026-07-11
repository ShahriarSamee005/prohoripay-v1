"""LLM explanation module (contract Phase 6).

Groq translates ALREADY-COMPUTED forecast/alert structs into natural-language
English / Bangla / Banglish. It is an explainer ONLY — it never calculates,
detects, scores, or decides. A strict post-generation safety guard plus a
deterministic template fallback guarantee the endpoint always returns safe,
usable text even when Groq is unavailable.

Strictly downstream: the forecast and alerts modules never import this package.
"""
