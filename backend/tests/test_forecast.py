"""Unit tests for the deterministic forecast engine (pure `forecast_pool`)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.modules.forecast.config import ForecastConfig
from app.modules.forecast.service import forecast_pool

ANCHOR = datetime(2026, 7, 11, 12, 0, 0)
CFG = ForecastConfig()  # defaults: analysis window 30, ema_span 10, thresholds 30/90


def _effects(mag_fn, sign: int = -1, cfg: ForecastConfig = CFG):
    """One effect per minute across the window; delta = sign * mag_fn(minute)."""
    ws = ANCHOR - timedelta(minutes=cfg.window_minutes)
    return [(ws + timedelta(minutes=i + 0.5), sign * mag_fn(i)) for i in range(cfg.window_minutes)]


# --------------------------------------------------------------- known-case math
def test_known_case_watch():
    """Constant 1000/min drain, 50k headroom -> ~50 min -> watch."""
    effects = _effects(lambda i: 1000)          # draining (sign -1)
    total = -1000 * CFG.window_minutes
    current = 60_000
    opening = current - total
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.current_balance == current
    assert abs(r.ema_burn_rate - 1000) < 10        # steady EMA of a constant series
    assert r.trend == "steady"
    assert abs(r.minutes_to_depletion - 50.0) < 1.0   # (60000-10000)/1000
    assert r.status.value == "watch"


def test_known_case_critical():
    """Same rate, only 10k headroom -> ~10 min -> critical."""
    effects = _effects(lambda i: 1000)
    total = -1000 * CFG.window_minutes
    current = 20_000
    opening = current - total
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert abs(r.minutes_to_depletion - 10.0) < 0.6
    assert r.status.value == "critical"
    # Countdown reconciles with the reported rate.
    headroom = r.current_balance - 10_000
    assert abs(headroom / r.burn_rate_per_min - r.minutes_to_depletion) < 0.6


# ------------------------------------------------------------------- filling pool
def test_filling_pool_has_null_countdown():
    """A pool gaining balance never depletes: null countdown, trend 'filling'."""
    effects = _effects(lambda i: 1000, sign=+1)   # filling (delta > 0)
    r = forecast_pool("bkash", effects, opening_balance=50_000, anchor=ANCHOR,
                      safety_floor=10_000, cfg=CFG)

    assert r.ema_burn_rate < 0                     # net inflow
    assert r.trend == "filling"
    assert r.minutes_to_depletion is None          # never negative
    assert r.projected_depletion_ts is None
    assert r.status.value == "healthy"


# ------------------------------------------------------------------------- trend
def test_accelerating_labeled_and_shortens_countdown():
    """A late-accelerating drain is 'accelerating' and beats the flat-EMA estimate."""
    # Earlier half @ 500/min, recent half @ 2000/min (a confirmed rising ramp).
    effects = _effects(lambda i: 500 if i < CFG.window_minutes // 2 else 2000)
    current = 100_000
    opening = current - sum(d for _, d in effects)
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.projection_state == "projected"
    assert r.trend == "accelerating"
    # Projecting with the higher recent rate yields a SHORTER countdown than the
    # flat EMA-only estimate would.
    headroom = r.current_balance - 10_000
    flat_ema_estimate = headroom / r.ema_burn_rate
    assert r.minutes_to_depletion < flat_ema_estimate


# -------------------------------------------------------------------- confidence
def test_steady_series_more_confident_than_volatile():
    steady = _effects(lambda i: 1000)
    volatile = _effects(lambda i: 2000 if (i // CFG.history_bucket_minutes) % 2 == 0 else 100)

    rs = forecast_pool("bkash", steady, 100_000, ANCHOR, 10_000, cfg=CFG)
    rv = forecast_pool("bkash", volatile, 100_000, ANCHOR, 10_000, cfg=CFG)

    assert rs.confidence > rv.confidence


def test_stale_meta_lowers_confidence():
    steady = _effects(lambda i: 1000)
    fresh = forecast_pool("bkash", steady, 100_000, ANCHOR, 10_000, data_freshness=1.0, cfg=CFG)
    stale = forecast_pool("bkash", steady, 100_000, ANCHOR, 10_000, data_freshness=0.5, cfg=CFG)

    assert stale.confidence < fresh.confidence
    assert abs(stale.confidence - fresh.confidence * 0.5) < 0.02   # ~halved (data freshness)


# ------------------------------------------- spike robustness (Rules 2 & 3)
def _spike_effects(baseline: int = 300, spike: int = 50_000, spike_minute: float = 22.5):
    """Calm steady drain across the window + ONE dominant cash-out near the end."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    effects = [(ws + timedelta(minutes=i + 0.5), -baseline) for i in range(CFG.window_minutes)]
    effects.append((ws + timedelta(minutes=spike_minute), -spike))
    return effects


def test_isolated_spike_stays_steady_with_pending_evidence():
    """Rule 3: a single dominant transaction is evidence, not acceleration.

    Trend stays 'steady', the countdown uses the EMA base (not the spike-shortened
    recent rate), and the pending-confirmation evidence is present with the amount.
    """
    effects = _spike_effects()
    current = 120_000
    opening = current - sum(d for _, d in effects)
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=20_000, cfg=CFG)

    assert r.trend == "steady"                       # NOT "accelerating"

    # Countdown reconciles with the EMA base rate, not a shortened recent rate.
    headroom = r.current_balance - 20_000
    assert r.burn_rate_per_min == round(r.ema_burn_rate)
    assert r.minutes_to_depletion == pytest.approx(headroom / r.ema_burn_rate, rel=0.02)

    # It is LONGER than the naive recent-window projection (the spike did NOT
    # shorten the countdown to the recent-rate level).
    recent_minutes = round(CFG.window_minutes * CFG.recent_fraction)
    naive_recent_rate = (recent_minutes * 300 + 50_000) / recent_minutes
    assert r.minutes_to_depletion > headroom / naive_recent_rate

    # Pending-confirmation evidence, calm language (never "accelerating" / a jump).
    joined = " ".join(r.evidence)
    assert "50,000" in joined
    assert "awaiting further activity to confirm sustained demand" in joined
    assert "accelerat" not in joined.lower()
    assert "burn rate increased" not in joined.lower()


def test_genuine_ramp_accelerates_and_shortens_countdown():
    """Rule 2 regression: a confirmed multi-reading ramp DOES accelerate.

    Three rising tiers (300 -> 900 -> 2,200 /min), none single-txn-dominated, give
    K+ consecutive EMA increases -> trend 'accelerating' and a shortened countdown.
    """
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    def rate(i):
        return 300 if i < 8 else (900 if i < 15 else 2_200)
    effects = [(ws + timedelta(minutes=i + 0.5), -rate(i)) for i in range(CFG.window_minutes)]
    current = 100_000
    opening = current - sum(d for _, d in effects)
    r = forecast_pool("physical_cash", effects, opening, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.projection_state == "projected"
    assert r.trend == "accelerating"
    # Projecting with the higher recent rate shortens the countdown vs a flat EMA.
    assert r.burn_rate_per_min > r.ema_burn_rate
    flat_ema_countdown = (r.current_balance - 10_000) / r.ema_burn_rate
    assert r.minutes_to_depletion < flat_ema_countdown
    # No spike wording — this is a genuine, sustained ramp.
    assert "awaiting further activity" not in " ".join(r.evidence)


def test_near_monotonic_wiggle_below_threshold_stays_steady():
    """Rule 2: a gentle rise whose cumulative change is below the threshold — with
    small wiggles — must NOT be mistaken for acceleration."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    def rate(i):
        return 1_000 + i * 4 + (60 if i % 2 == 0 else -60)   # slope 4/min + ±60 wiggle
    effects = [(ws + timedelta(minutes=i + 0.5), -rate(i)) for i in range(CFG.window_minutes)]
    r = forecast_pool("bkash", effects, 100_000, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.trend == "steady"                       # cumulative rise < threshold


def test_isolated_spike_does_not_jump_confidence():
    """Rule 3: an unconfirmed single-transaction jump must not inflate confidence."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    calm = [(ws + timedelta(minutes=i + 0.5), -300) for i in range(CFG.window_minutes)]
    spike = calm + [(ws + timedelta(minutes=22.5), -50_000)]

    calm_r = forecast_pool("physical_cash", calm, 120_000 - sum(d for _, d in calm),
                           ANCHOR, safety_floor=20_000, cfg=CFG)
    spike_r = forecast_pool("physical_cash", spike, 120_000 - sum(d for _, d in spike),
                            ANCHOR, safety_floor=20_000, cfg=CFG)

    assert spike_r.confidence <= calm_r.confidence   # the lone spike gives no boost


def test_spike_precedence_over_confirmed_ramp():
    """Rule 3 precedence: a jump that is BOTH single-txn-dominated AND would pass
    Rule 2 must NOT accelerate — it stays steady with pending-confirmation evidence.
    """
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    def rate(i):
        return 300 if i < 8 else (900 if i < 15 else 2_200)   # a confirmed rising ramp
    ramp = [(ws + timedelta(minutes=i + 0.5), -rate(i)) for i in range(CFG.window_minutes)]

    # Baseline: the ramp alone genuinely accelerates (Rule 2 fires).
    r_ramp = forecast_pool("physical_cash", ramp, 100_000 - sum(d for _, d in ramp),
                           ANCHOR, safety_floor=10_000, cfg=CFG)
    assert r_ramp.trend == "accelerating"

    # Same ramp + ONE dominant transaction in the recent window (Rule 3 applies).
    with_spike = ramp + [(ws + timedelta(minutes=25), -80_000)]
    r = forecast_pool("physical_cash", with_spike, 200_000 - sum(d for _, d in with_spike),
                      ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.projection_state == "projected"
    assert r.trend == "steady"                       # precedence: spike beats Rule 2
    joined = " ".join(r.evidence)
    assert "awaiting further activity to confirm sustained demand" in joined
    assert "accelerat" not in joined.lower()
    assert "burn rate increased" not in joined.lower()


# ----------------------------------- sustained vs intermittent + horizon states
def test_burst_gap_burst_is_intermittent_and_watching():
    """Burst -> long quiet gap -> burst: intermittent, null countdown, WATCHING."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    # 3 txns near the start, a >15-min quiet gap, then 3 txns near the end.
    minutes = (1, 2, 3, 25, 26, 27)
    effects = [(ws + timedelta(minutes=m), -3_000) for m in minutes]
    r = forecast_pool("physical_cash", effects, 100_000, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.projection_state == "intermittent"
    assert r.minutes_to_depletion is None
    assert r.projected_depletion_ts is None
    assert r.trend == "steady"
    # It is a WATCHING state — never presented as "no shortage" / all-clear.
    assert r.status.value == "watch"
    # Confidence is reduced vs a comparable sustained series.
    sustained = _effects(lambda i: 100)   # regular spacing, steady drain
    r_sustained = forecast_pool("physical_cash", sustained,
                                100_000 - sum(d for _, d in sustained),
                                ANCHOR, safety_floor=10_000, cfg=CFG)
    assert r.confidence < r_sustained.confidence
    # Bursts are surfaced in the evidence.
    assert any("intermittent" in e.lower() and "burst" in e.lower() for e in r.evidence)


def test_two_clusters_both_inside_window_are_both_in_ema():
    """Two clusters both within ANALYSIS_WINDOW_MINUTES both influence the EMA
    (the older one is NOT silently dropped while still in the window)."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    older = [(ws + timedelta(minutes=m), -2_000) for m in (3, 4, 5, 6, 7)]
    recent = [(ws + timedelta(minutes=m), -2_000) for m in (20, 21, 22, 23, 24)]

    r_recent_only = forecast_pool("physical_cash", recent,
                                  100_000 - sum(d for _, d in recent),
                                  ANCHOR, safety_floor=10_000, cfg=CFG)
    r_both = forecast_pool("physical_cash", older + recent,
                           100_000 - sum(d for _, d in older + recent),
                           ANCHOR, safety_floor=10_000, cfg=CFG)

    # The older in-window cluster raises the EMA — it is reflected, not dropped.
    assert r_both.ema_burn_rate > r_recent_only.ema_burn_rate


def test_gap_longer_than_window_ages_out_earlier_cluster():
    """A cluster more than ANALYSIS_WINDOW_MINUTES before 'now' has aged out and
    does not influence the forecast — only the recent cluster is considered."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    recent = [(ws + timedelta(minutes=m), -2_000) for m in (25, 26, 27)]
    # A cluster 15 min BEFORE the window even starts (fully aged out).
    aged_out = [(ws - timedelta(minutes=15) + timedelta(minutes=m), -2_000) for m in (0, 1, 2)]

    r_recent = forecast_pool("physical_cash", recent, 100_000, ANCHOR,
                             safety_floor=10_000, cfg=CFG)
    r_with_aged = forecast_pool("physical_cash", aged_out + recent,
                                100_000 - sum(d for _, d in aged_out),
                                ANCHOR, safety_floor=10_000, cfg=CFG)

    # Identical rate: the aged-out cluster is bridged as independent, not counted.
    assert r_with_aged.ema_burn_rate == r_recent.ema_burn_rate


def test_insufficient_data_is_watching_not_all_clear():
    """Too few txns => insufficient_data: null countdown, reduced confidence, and a
    WATCHING presentation — never 'no shortage'."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    effects = [(ws + timedelta(minutes=5), -3_000), (ws + timedelta(minutes=20), -3_000)]
    r = forecast_pool("physical_cash", effects, 100_000, ANCHOR, safety_floor=10_000, cfg=CFG)

    assert r.projection_state == "insufficient_data"
    assert r.minutes_to_depletion is None
    assert r.status.value == "watch"                 # watching, not healthy/all-clear
    assert any("low-confidence" in e.lower() and "monitor" in e.lower() for e in r.evidence)
    # Nothing anywhere claims there is no shortage.
    assert not any("no near-term shortage" in e.lower() for e in r.evidence)


def test_regular_spacing_and_draining_is_projected():
    """Enough regularly-spaced draining txns => projected with a real countdown."""
    effects = _effects(lambda i: 1_000)             # one per minute, steady drain
    r = forecast_pool("physical_cash", effects, 60_000 - sum(d for _, d in effects),
                      ANCHOR, safety_floor=10_000, cfg=CFG)
    assert r.projection_state == "projected"
    assert r.minutes_to_depletion is not None
    assert abs(r.minutes_to_depletion - 50.0) < 1.0   # (60000-10000)/1000


def test_rate_near_zero_yields_null_without_exception():
    """A projection rate at/below epsilon => null countdown, no divide-by-zero."""
    effects = _effects(lambda i: 1_000)
    cfg = replace(CFG, rate_epsilon=10 ** 9)          # force rate <= epsilon
    r = forecast_pool("physical_cash", effects, 60_000 - sum(d for _, d in effects),
                      ANCHOR, safety_floor=10_000, cfg=cfg)
    assert r.projection_state == "projected"
    assert r.minutes_to_depletion is None
    assert any("no near-term shortage" in e.lower() for e in r.evidence)


def test_beyond_horizon_reports_no_near_term_shortage():
    """A very slow drain projecting beyond MAX_HORIZON => null countdown + a
    'no near-term shortage' message, not an inflated raw number."""
    effects = _effects(lambda i: 30)                  # ~30 BDT/min over a big headroom
    current = 100_000
    r = forecast_pool("physical_cash", effects, current - sum(d for _, d in effects),
                      ANCHOR, safety_floor=20_000, cfg=CFG)
    assert r.projection_state == "projected"
    assert r.minutes_to_depletion is None             # (80000/30 ≈ 2666 > 1440)
    assert any("no near-term shortage" in e.lower() for e in r.evidence)


def test_single_txn_crossing_floor_is_at_floor_now():
    """Rule 5: one txn taking balance at/below the safety floor is an at-floor state
    NOW — surfaced directly, not routed through the rate model."""
    ws = ANCHOR - timedelta(minutes=CFG.window_minutes)
    effects = [(ws + timedelta(minutes=25), -10_000)]   # opening 25k -> current 15k
    r = forecast_pool("physical_cash", effects, opening_balance=25_000, anchor=ANCHOR,
                      safety_floor=20_000, cfg=CFG)

    assert r.projection_state == "at_floor"
    assert r.current_balance == 15_000
    assert r.minutes_to_depletion == 0.0
    assert r.status.value == "critical"
    assert any("safety reserve" in e.lower() and "20,000" in e for e in r.evidence)
