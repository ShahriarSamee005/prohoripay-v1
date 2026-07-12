"""Tests for temporal seasonality profile, time-aware anomaly baselines,
and the salary-day inverse-stress scenario.

Coverage:
- HOUR_MULTIPLIERS completeness and shape.
- Normal high volume at a BUSY hour is NOT flagged (baseline absorbs it).
- Same volume at a QUIET hour IS flagged, evidence cites the hour's expected rate.
- Salary-day scenario: bKash provider float drains to critical while physical cash
  stays healthy — the inverse of the default Eid scenario.
- False-positive rate re-measured after seasonality changes (must not worsen).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.enums import PoolId, TxnType
from app.core.models import Pool, Transaction
from app.modules.alerts.config import DEFAULT_DETECTOR_CONFIG as CFG
from app.modules.alerts.detectors import detect_off_hours
from app.modules.synth import config as synth_cfg
from app.modules.synth.generator import populate_salary_day

DAY = datetime(2026, 7, 11)


def _txn(i, provider, amount, ts, account, event_flag=None):
    return {
        "id": f"t{i}", "ts": ts, "provider": provider, "amount": amount,
        "account_id": account, "event_flag": event_flag, "txn_type": "cash_out",
    }


# ---------------------------------------------------------------- seasonality profile
def test_hour_multipliers_cover_all_24_hours():
    """Every hour 0–23 must have a multiplier in (0, 1]."""
    mults = CFG.hour_multipliers
    assert len(mults) == 24
    for h in range(24):
        assert h in mults, f"hour {h} missing"
        assert 0 < mults[h] <= 1.0, f"hour {h} multiplier {mults[h]} out of (0, 1]"


def test_synth_and_detector_hour_multipliers_match():
    """The synth config and alert detector must share the same seasonality profile."""
    assert synth_cfg.HOUR_MULTIPLIERS == CFG.hour_multipliers


def test_peak_hours_have_highest_multiplier():
    """Midday hours (10–11) should share the peak multiplier."""
    mults = CFG.hour_multipliers
    peak = max(mults.values())
    peak_hours = {h for h, m in mults.items() if m == peak}
    assert peak_hours & {10, 11}, f"hours 10–11 not at peak; peak at {peak_hours}"


def test_overnight_lower_than_midday():
    """Hours 0–5 must all be lower than any midday hour (10–12)."""
    mults = CFG.hour_multipliers
    assert max(mults[h] for h in range(0, 6)) < min(mults[h] for h in range(10, 13))


def test_day_of_month_salary_week_elevated():
    """Days 1–7 must have higher multipliers than mid-month days."""
    salary = min(synth_cfg.DAY_OF_MONTH_MULTIPLIERS[d] for d in range(1, 8))
    normal = max(synth_cfg.DAY_OF_MONTH_MULTIPLIERS[d] for d in range(8, 29))
    assert salary > normal


# ------------------------------------------------ time-aware off-hours baselines
def test_quiet_hour_burst_flagged_with_baseline_evidence():
    """10 txns in 10 min at 03:00 (mult=0.02) must flag with evidence citing the rate."""
    base = DAY + timedelta(hours=3)
    txns = [_txn(i, "nagad", 2_000, base + timedelta(minutes=i), f"ACC_{i}")
            for i in range(10)]
    findings = detect_off_hours(txns, CFG)

    assert len(findings) == 1, "burst at 03:00 must be flagged"
    f = findings[0]
    assert f.anomaly_type == "off_hours_burst"

    evidence_text = " ".join(f.evidence)
    assert "txn/min" in evidence_text, "evidence must cite txn/min rate"
    assert "hour" in evidence_text.lower(), "evidence must mention the hour"
    assert "expected" in evidence_text.lower(), "evidence must cite expected baseline"


def test_quiet_hour_finding_baseline_dict_has_hour_multiplier():
    """The baseline dict in the finding must record the hour's multiplier."""
    base = DAY + timedelta(hours=3)
    txns = [_txn(i, "nagad", 2_000, base + timedelta(minutes=i), f"ACC_{i}")
            for i in range(10)]
    findings = detect_off_hours(txns, CFG)

    assert findings
    baseline = findings[0].baseline
    assert "hour_multiplier" in baseline
    assert "txn_per_min_expected" in baseline
    assert baseline["hour_multiplier"] == CFG.hour_multipliers[3]
    # Expected rate = base_rate * multiplier
    assert abs(baseline["txn_per_min_expected"] - CFG.off_hours_base_rate * CFG.hour_multipliers[3]) < 1e-6


def test_busy_hour_same_volume_not_flagged():
    """10 txns in 10 min at 14:00 (mult=0.80, non-event) must NOT flag.

    This is the critical time-aware property: the SAME absolute volume that triggers
    a flag at 03:00 is absorbed by the higher expected baseline at 14:00.
    """
    base = DAY + timedelta(hours=14)
    txns = [_txn(i, "nagad", 2_000, base + timedelta(minutes=i), f"ACC_{i}")
            for i in range(10)]
    # Hour 14 observed: ~1 txn/min; expected: 0.20 * 0.80 = 0.16/min; ratio 6.25 < 8.0 → no flag
    findings = detect_off_hours(txns, CFG)

    assert findings == [], (
        f"burst at 14:00 (high-multiplier hour) must not be flagged; got {findings}"
    )


def test_ratio_in_evidence_exceeds_threshold():
    """The evidence string for a quiet-hour burst must show ratio > threshold."""
    base = DAY + timedelta(hours=3)
    txns = [_txn(i, "nagad", 2_000, base + timedelta(minutes=i), f"ACC_{i}")
            for i in range(10)]
    findings = detect_off_hours(txns, CFG)

    assert findings
    evidence_text = " ".join(findings[0].evidence)
    # Evidence contains something like "250× expected" or similar large ratio.
    import re
    match = re.search(r"(\d+)× expected", evidence_text)
    assert match, f"evidence must contain 'N× expected'; got: {evidence_text}"
    ratio = int(match.group(1))
    assert ratio >= CFG.off_hours_relative_threshold


# -------------------------------------------------------- salary-day fixture
@pytest.fixture(scope="module")
def salary_day_session(tmp_path_factory):
    """Isolated SQLite DB seeded with the salary-day (cash-in heavy) scenario."""
    from app.core import models  # noqa: F401 — registers tables on SQLModel.metadata
    from app.modules.cases import models as _cm  # noqa: F401

    db_path = tmp_path_factory.mktemp("salary_db") / "salary_day.db"
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        populate_salary_day(s)
    with Session(eng) as s:
        yield s


# ----------------------------------------------------- salary-day scenario tests
def test_salary_day_bkash_is_constraining_pool(salary_day_session: Session):
    """bKash must be critical while physical cash stays healthy — inverse of Eid."""
    pools = {p.pool_id: p for p in salary_day_session.exec(select(Pool)).all()}

    bkash = pools["bkash"]
    physical = pools[PoolId.physical_cash.value]

    # bKash drained by heavy cash-in → critical.
    assert bkash.status.value == "critical", (
        f"bKash should be critical; got {bkash.status.value} "
        f"(current={bkash.current_balance:,}, opening={bkash.opening_balance:,})"
    )
    assert bkash.current_balance < bkash.opening_balance, "bKash must have drained"

    # Physical cash grew from cash-in → healthy.
    assert physical.current_balance > physical.opening_balance, (
        "physical cash should have grown under cash-in pressure"
    )
    assert physical.status.value == "healthy", (
        f"physical cash should be healthy in salary-day scenario; got {physical.status.value}"
    )


def test_salary_day_inverse_stress_pattern(salary_day_session: Session):
    """Combined total looks healthy even though bKash is the constraining pool."""
    pools = {p.pool_id: p for p in salary_day_session.exec(select(Pool)).all()}
    bkash = pools["bkash"]
    physical = pools[PoolId.physical_cash.value]

    # The total across all non-interchangeable pools looks healthy...
    total = sum(p.current_balance for p in pools.values())
    assert total > bkash.current_balance * 5, "total must dwarf the constrained bKash pool"

    # ...but bKash specifically is well below its opening.
    drain_pct = (bkash.opening_balance - bkash.current_balance) / bkash.opening_balance
    assert drain_pct > 0.20, f"bKash should drain >20%; actual drain {drain_pct:.1%}"


def test_salary_day_direction_rule_holds(salary_day_session: Session):
    """Direction rule: cash_in -> physical_cash +, provider -; cash_out -> opposite."""
    txns = salary_day_session.exec(select(Transaction)).all()
    assert txns, "salary-day session must have transactions"
    for txn in txns:
        phys = next(e["delta"] for e in txn.pool_effects
                    if e["pool_id"] == PoolId.physical_cash.value)
        prov = next(e["delta"] for e in txn.pool_effects if e["pool_id"] == txn.provider)
        assert txn.amount > 0
        assert abs(phys) == txn.amount
        assert abs(prov) == txn.amount
        if txn.txn_type == TxnType.cash_out:
            assert phys < 0 and prov > 0
        else:
            assert phys > 0 and prov < 0


def test_salary_day_balance_integrity(salary_day_session: Session):
    """current_balance == opening_balance + sum(signed effects) for every pool."""
    pools = salary_day_session.exec(select(Pool)).all()
    txns = salary_day_session.exec(select(Transaction)).all()
    net: dict[str, int] = {}
    for txn in txns:
        for eff in txn.pool_effects:
            net[eff["pool_id"]] = net.get(eff["pool_id"], 0) + eff["delta"]
    for pool in pools:
        expected = pool.opening_balance + net.get(pool.pool_id, 0)
        assert pool.current_balance == expected, (
            f"{pool.pool_id}: stored {pool.current_balance} != opening {pool.opening_balance} "
            f"+ net {net.get(pool.pool_id, 0)}"
        )


# ----------------------------------------- FP rate re-measurement post-seasonality
def test_false_positive_rate_unchanged_after_seasonality(db_session, capsys):
    """Re-measure FP rate on the existing Eid dataset — must remain 0.0."""
    from app.modules.alerts.metrics import false_positive_rate
    fp = false_positive_rate(db_session)

    assert fp["fp_rate"] == 0.0, (
        f"FP rate must remain 0.0 after seasonality changes; got {fp['fp_rate']}"
    )

    with capsys.disabled():
        print(
            f"\n[FP RATE after seasonality] {fp['fp_rate']} "
            f"({fp['false_positive_alerts']}/{fp['total_anomaly_alerts']} alerts false); "
            f"{fp['normal_event_txns_incidentally_covered']}/{fp['normal_event_txns']} "
            f"normal Eid txns incorrectly covered — seasonality baseline absorbed demand."
        )
