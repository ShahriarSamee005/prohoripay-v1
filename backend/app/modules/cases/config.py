"""Tunable constants for case routing, SLAs, and the escalation ladder.

All coordination policy lives here so it is reproducible and Phase 5 can drive
auto-escalation from the sim clock without touching the state machine. Nothing in
this module is a financial action — it only assigns, tracks, and recommends.
"""

from __future__ import annotations

# --------------------------------------------------------------- routing by type
# Which role first owns a case, keyed by the alert's type. Provider-respecting:
# a case only ever concerns its own provider's data.
ROUTING: dict[str, str] = {
    "liquidity": "field_officer",
    "anomaly": "risk_reviewer",
}

# Time budget (minutes) before auto-escalation is due, keyed by alert type.
SLA_MINUTES: dict[str, int] = {
    "liquidity": 15,   # liquidity pressure is time-critical
    "anomaly": 30,     # review clusters get a longer window
}

# The ladder a case climbs on each escalation. escalation_level 0 is the base
# owner (from ROUTING); level 1 -> LADDER[0], level 2+ -> LADDER[-1] (capped top).
ESCALATION_LADDER: tuple[str, ...] = ("supervisor", "area_manager")

# All roles that can own a case (base owners + ladder), for validation/reference.
OWNER_ROLES: frozenset[str] = frozenset(
    {"field_officer", "risk_reviewer", *ESCALATION_LADDER}
)

# ---------------------------------------------------------------- state machine
# Case statuses (contract). `resolved` is terminal.
STATUSES: tuple[str, ...] = ("raised", "routed", "acknowledged", "escalated", "resolved")

# Guarded transitions: action -> (allowed source statuses, destination status).
# A second `escalate` (escalated -> escalated) is allowed so a case can climb the
# ladder more than once; auto-escalation reuses the same path.
ALLOWED_TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "ack": (frozenset({"routed"}), "acknowledged"),
    "escalate": (frozenset({"routed", "acknowledged", "escalated"}), "escalated"),
    "resolve": (frozenset({"acknowledged", "escalated"}), "resolved"),
}


def escalated_owner(new_level: int) -> str:
    """Owner role after climbing to `new_level` (>=1) on the ladder (capped top)."""
    idx = min(new_level, len(ESCALATION_LADDER)) - 1
    return ESCALATION_LADDER[idx]
