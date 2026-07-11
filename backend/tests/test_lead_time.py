"""Validation metric: shortage-detection lead time (a required deliverable metric)."""

from __future__ import annotations

from app.modules.forecast.metrics import measure_lead_time


def test_lead_time_is_positive_and_auditable(db_session, capsys):
    m = measure_lead_time(db_session)

    # We must flag critical BEFORE the drawer actually crosses its safety floor.
    assert m["lead_time_minutes"] is not None
    assert m["first_critical_minutes"] is not None
    assert m["lead_time_minutes"] > 0
    assert m["first_critical_minutes"] < m["actual_depletion_minutes"]

    # Print the number for the deliverable (visible with `pytest -s`).
    with capsys.disabled():
        print(
            "\n[METRIC] Shortage detection lead time = "
            f"{m['lead_time_minutes']} min "
            f"(critical at +{m['first_critical_minutes']}m, "
            f"actual depletion at +{m['actual_depletion_minutes']}m, "
            f"drain ~{m['burn_rate_per_min']:,} BDT/min)"
        )
