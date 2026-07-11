"""API-level forecast tests: contract shape, direction sanity, pools/forecast agreement."""

from __future__ import annotations

from app.modules.forecast.service import compute_forecasts

_META_KEYS = {"generated_at", "data_quality", "confidence_modifier"}
_CONTRACT_KEYS = {
    "pool_id", "current_balance", "burn_rate_per_min", "minutes_to_depletion",
    "projected_depletion_ts", "confidence", "recommended_action", "evidence",
}
_ADDITIVE_KEYS = {"status", "trend", "confidence_factors", "history"}


def test_forecast_endpoint_shape(client):
    resp = client.get("/api/forecast")
    assert resp.status_code == 200
    body = resp.json()

    assert _META_KEYS <= body["meta"].keys()
    forecasts = body["forecasts"]
    assert len(forecasts) == 4
    assert forecasts[0]["pool_id"] == "physical_cash"  # shared pool first

    for f in forecasts:
        assert _CONTRACT_KEYS <= f.keys()          # every contract field present
        assert _ADDITIVE_KEYS <= f.keys()          # plus the Phase-2 additions
        assert 0.0 <= f["confidence"] <= 1.0
        assert isinstance(f["evidence"], list) and 2 <= len(f["evidence"]) <= 4
        assert f["trend"] in {"accelerating", "easing", "steady", "filling"}
        assert f["status"] in {"healthy", "watch", "critical"}
        # Countdown and depletion timestamp are consistently present or absent.
        assert (f["minutes_to_depletion"] is None) == (f["projected_depletion_ts"] is None)
        # confidence_factors breakdown is exposed.
        assert {"variance_factor", "sample_factor", "data_freshness", "sample_size"} <= \
            f["confidence_factors"].keys()


def test_soonest_depletion_is_derivable(client):
    """The hero's constraining pool = soonest minutes_to_depletion is trivially found."""
    forecasts = client.get("/api/forecast").json()["forecasts"]
    depleting = [f for f in forecasts if f["minutes_to_depletion"] is not None]
    assert depleting, "expected at least one depleting pool in the seeded scenario"
    soonest = min(depleting, key=lambda f: f["minutes_to_depletion"])
    # In the hidden-shortage scenario, physical cash is the constraint.
    assert soonest["pool_id"] == "physical_cash"


def test_direction_sanity(db_session):
    """Physical cash drains under cash-out pressure; a credited provider fills."""
    res = {r.pool_id: r for r in compute_forecasts(db_session)}

    physical = res["physical_cash"]
    assert physical.ema_burn_rate > 0                       # draining
    assert physical.trend in {"accelerating", "easing", "steady"}
    assert physical.minutes_to_depletion is not None

    bkash = res["bkash"]
    assert bkash.ema_burn_rate < 0                          # filling (credited)
    assert bkash.trend == "filling"
    assert bkash.minutes_to_depletion is None


def test_pools_status_matches_forecast_for_every_pool(client):
    pools = {p["pool_id"]: p["status"] for p in client.get("/api/pools").json()["pools"]}
    forecast = {f["pool_id"]: f["status"] for f in client.get("/api/forecast").json()["forecasts"]}
    assert pools == forecast


def test_recommended_actions_are_safe_and_provider_respecting(client):
    """No cross-provider transfer language anywhere; safe, advisory wording."""
    forecasts = client.get("/api/forecast").json()["forecasts"]
    banned = ("fraud", "suspicious", "criminal", "block", "transfer from", "move from")
    for f in forecasts:
        action = f["recommended_action"].lower()
        assert not any(b in action for b in banned)
