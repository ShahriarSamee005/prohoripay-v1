"""Unit tests for the pure, deterministic detectors and the context gate."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.modules.alerts.config import DEFAULT_DETECTOR_CONFIG as CFG
from app.modules.alerts.detectors import (
    classify_surge,
    detect_balance_inconsistency,
    detect_off_hours,
    detect_structuring,
    detect_velocity,
)

DAY = datetime(2026, 7, 11)


def _txn(i, provider, amount, ts, account):
    return {"id": f"t{i}", "ts": ts, "provider": provider, "amount": amount,
            "account_id": account, "event_flag": None, "txn_type": "cash_out"}


# --------------------------------------------------------------- structuring
def test_structuring_detects_repeated_amounts_from_small_cluster():
    base = DAY + timedelta(hours=11)
    # 10 near-identical (~4,950) txns from 3 accounts within 30 min.
    txns = [_txn(i, "bkash", 4950 + (i % 3) * 10, base + timedelta(minutes=i * 3),
                 f"ACC_900{i % 3}") for i in range(10)]
    # plus spread-out normal traffic from many distinct accounts, varied amounts.
    txns += [_txn(100 + i, "bkash", 1000 + i * 700, base + timedelta(minutes=i * 5),
                  f"ACC_{2000 + i}") for i in range(10)]

    findings = detect_structuring(txns, CFG)
    assert len(findings) == 1
    f = findings[0]
    assert f.anomaly_type == "structuring"
    assert f.observed["distinct_accounts"] == 3
    assert f.observed["transactions"] >= CFG.struct_min_count
    assert all("BDT" in e or "accounts" in e or "minutes" in e for e in f.evidence)


def test_structuring_ignores_diverse_normal_traffic():
    base = DAY + timedelta(hours=10)
    txns = [_txn(i, "bkash", 1000 + i * 500, base + timedelta(minutes=i * 2),
                 f"ACC_{3000 + i}") for i in range(20)]
    assert detect_structuring(txns, CFG) == []


# ----------------------------------------------------------------- velocity
def test_velocity_detects_burst():
    base = DAY + timedelta(hours=3)   # non-event hour so context doesn't raise the bar
    # sparse baseline
    txns = [_txn(i, "rocket", 2000, base + timedelta(minutes=i * 20), f"ACC_{i}")
            for i in range(3)]
    # burst: 15 txns in 4 minutes from 2 accounts
    burst_start = base + timedelta(minutes=90)
    txns += [_txn(500 + i, "rocket", 2000, burst_start + timedelta(seconds=i * 15),
                  f"ACC_91{i % 2}") for i in range(15)]

    findings = detect_velocity(txns, CFG)
    assert len(findings) == 1
    assert findings[0].anomaly_type == "velocity_spike"
    assert findings[0].observed["transactions"] >= CFG.velocity_min_count


# ---------------------------------------------------------------- off-hours
def test_off_hours_detects_quiet_hour_cluster():
    base = DAY + timedelta(hours=3, minutes=5)   # 03:05, quiet + no event
    txns = [_txn(i, "nagad", 3000, base + timedelta(minutes=i * 3), f"ACC_92{i % 2}")
            for i in range(8)]
    findings = detect_off_hours(txns, CFG)
    assert len(findings) == 1
    assert findings[0].anomaly_type == "off_hours_burst"


def test_off_hours_ignores_daytime_activity():
    base = DAY + timedelta(hours=11)
    txns = [_txn(i, "nagad", 3000, base + timedelta(minutes=i * 3), f"ACC_{i}")
            for i in range(8)]
    assert detect_off_hours(txns, CFG) == []


# --------------------------------------------------------- balance inconsistency
def test_balance_inconsistency_flags_mismatch_and_ignores_consistent():
    consistent = [{"pool_id": "bkash", "provider": "bkash", "opening_balance": 100_000,
                   "current_balance": 120_000, "ts": DAY}]
    assert detect_balance_inconsistency(consistent, {"bkash": 20_000}, CFG) == []

    mismatch = [{"pool_id": "bkash", "provider": "bkash", "opening_balance": 100_000,
                 "current_balance": 999_999, "ts": DAY}]
    findings = detect_balance_inconsistency(mismatch, {"bkash": 20_000}, CFG)
    assert len(findings) == 1
    assert findings[0].anomaly_type == "balance_inconsistency"


# ------------------------------------------------- context-aware baseline (FP ctrl)
def test_context_recognizes_eid_surge_as_expected():
    """A 5x Eid surge is EXPECTED with context, but a naive threshold flags it."""
    baseline_per_min = 500 / 60      # normal 500/hr
    observed_per_min = 2500 / 60     # Eid 2500/hr (5x)

    with_ctx, note_ctx = classify_surge(observed_per_min, baseline_per_min,
                                        within_event="eid_rush", cfg=CFG, use_context=True)
    without_ctx, note_naive = classify_surge(observed_per_min, baseline_per_min,
                                             within_event="eid_rush", cfg=CFG, use_context=False)
    assert with_ctx == "expected"     # context: recognized as expected demand
    assert without_ctx == "review"    # naive: would be a false positive
    assert "eid_rush" in note_ctx


def test_context_flags_off_hours_surge_with_no_event():
    """The 3 AM surge with no known event is 'review' regardless of context."""
    cls, _ = classify_surge(2500 / 60, 20 / 60, within_event=None, cfg=CFG, use_context=True)
    assert cls == "review"
