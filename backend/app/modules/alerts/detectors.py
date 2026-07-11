"""Pure, deterministic anomaly detectors (rules primary — NO LLM, no DB).

Each detector consumes plain transaction records and returns `Finding`s carrying
human-readable EVIDENCE (never a bare score) plus baseline/observed comparisons.
Detectors are context-aware: the known-event calendar raises the baseline so a
legitimate Eid surge is NOT flagged (see `classify_surge` and the velocity path).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.enums import PoolId
from app.modules.alerts.config import (
    DEFAULT_DETECTOR_CONFIG,
    EVENT_CALENDAR,
    DetectorConfig,
    EventWindow,
)

# A transaction record the detectors operate on.
Txn = dict  # {id, ts: datetime, provider, amount, account_id, event_flag, txn_type}


@dataclass
class Finding:
    """One detected anomaly cluster with its evidence and coverage."""

    anomaly_type: str
    provider: str
    pool_id: str
    evidence: list[str]
    baseline: dict
    observed: dict
    strength: float                  # 0..1, mapped to confidence by the service
    covered_txn_ids: list[str]
    ts: datetime                     # representative (most recent) time of the cluster
    within_event: str | None = None
    accounts: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- utils
def _group_by_provider(txns: list[Txn]) -> dict[str, list[Txn]]:
    out: dict[str, list[Txn]] = {}
    for t in txns:
        out.setdefault(t["provider"], []).append(t)
    for items in out.values():
        items.sort(key=lambda t: t["ts"])
    return out


def active_event(ts: datetime, calendar: tuple[EventWindow, ...] = EVENT_CALENDAR) -> str | None:
    """Return the name of the known event active at `ts`, or None."""
    sec = ts.hour * 3600 + ts.minute * 60 + ts.second
    for ev in calendar:
        if ev.start_sec <= sec < ev.end_sec:
            return ev.name
    return None


def _distinct_accounts(items: list[Txn]) -> list[str]:
    return sorted({t["account_id"] for t in items})


def _span_minutes(items: list[Txn]) -> float:
    if len(items) < 2:
        return 0.0
    return (items[-1]["ts"] - items[0]["ts"]).total_seconds() / 60.0


def _fmt_hm(ts: datetime) -> str:
    return ts.strftime("%H:%M")


# ---------------------------------------------------------------- context surge gate
def classify_surge(
    observed_rate: float,
    baseline_rate: float,
    within_event: str | None,
    cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG,
    use_context: bool = True,
) -> tuple[str, str]:
    """Classify a pure-volume surge as 'expected' or 'review'.

    The context-aware baseline is the false-positive control: during a known
    event the bar is raised (`event_rate_multiplier`), so an ordinary Eid surge
    is recognized as expected demand instead of being flagged. With `use_context`
    off (the naive path) the same surge trips the plain `volume_surge_factor`.
    """
    if within_event and use_context:
        if observed_rate >= baseline_rate * cfg.event_rate_multiplier:
            return "review", f"volume far exceeds even the raised {within_event} baseline"
        return "expected", f"high volume recognized as expected {within_event} demand"
    # No context (or no active event): plain relative threshold.
    if observed_rate >= baseline_rate * cfg.volume_surge_factor:
        return "review", "volume above baseline with no known event to explain it"
    return "expected", "volume within normal range"


# ------------------------------------------------------------------ structuring
def _densest_window(items: list[Txn], window_minutes: float, min_count: int,
                    max_accounts: int) -> list[Txn] | None:
    """Largest time-window (<= window) sub-run with >= min_count and <= max_accounts."""
    items = sorted(items, key=lambda t: t["ts"])
    best: list[Txn] | None = None
    left = 0
    for right in range(len(items)):
        while (items[right]["ts"] - items[left]["ts"]).total_seconds() / 60.0 > window_minutes:
            left += 1
        window = items[left:right + 1]
        if len(window) >= min_count and len(_distinct_accounts(window)) <= max_accounts:
            if best is None or len(window) > len(best):
                best = list(window)
    return best


def detect_structuring(txns: list[Txn], cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG) -> list[Finding]:
    """Many near-identical amounts from a small account cluster in a short window.

    Amount-clustering + account concentration — NOT raw volume — so a normal Eid
    surge (many distinct accounts, varied amounts) never triggers this.
    """
    findings: list[Finding] = []
    for provider, items in _group_by_provider(txns).items():
        used: set[str] = set()
        for anchor in items:
            if anchor["id"] in used:
                continue
            amt = anchor["amount"]
            tol = amt * cfg.struct_amount_rel
            similar = [t for t in items if abs(t["amount"] - amt) <= tol]
            if len(similar) < cfg.struct_min_count:
                continue
            cluster = _densest_window(similar, cfg.struct_window_minutes,
                                      cfg.struct_min_count, cfg.struct_max_accounts)
            if not cluster or any(t["id"] in used for t in cluster):
                continue
            used.update(t["id"] for t in cluster)

            amounts = [t["amount"] for t in cluster]
            accounts = _distinct_accounts(cluster)
            mean_amt = round(sum(amounts) / len(amounts))
            span = _span_minutes(cluster)
            spread = (max(amounts) - min(amounts)) / mean_amt if mean_amt else 0.0
            findings.append(Finding(
                anomaly_type="structuring",
                provider=provider,
                pool_id=provider,
                evidence=[
                    f"{len(cluster)} transactions of ~{mean_amt:,} BDT (near-identical amounts)",
                    f"from {len(accounts)} accounts",
                    f"within {round(span)} minutes",
                ],
                baseline={"distinct_accounts_expected": ">10 for this volume"},
                observed={"transactions": len(cluster), "distinct_accounts": len(accounts),
                          "amount_spread_pct": round(spread * 100, 1)},
                strength=min(1.0, 0.4 + 0.05 * len(cluster) + 0.1 * (cfg.struct_max_accounts - len(accounts))),
                covered_txn_ids=[t["id"] for t in cluster],
                ts=cluster[-1]["ts"],
                within_event=active_event(cluster[-1]["ts"]),
                accounts=accounts,
            ))
    return findings


# --------------------------------------------------------------------- velocity
def _baseline_rate_per_min(items: list[Txn], cfg: DetectorConfig) -> float:
    """Per-minute rate from NON-event transactions (the quiet, expected pace)."""
    non_event = [t for t in items if active_event(t["ts"]) is None]
    if len(non_event) < 2:
        return cfg.velocity_min_baseline_rate
    span = max(1.0, _span_minutes(non_event))
    return max(cfg.velocity_min_baseline_rate, len(non_event) / span)


def detect_velocity(txns: list[Txn], cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG,
                    use_context: bool = True) -> list[Finding]:
    """A burst whose rate is far above the event-adjusted baseline."""
    findings: list[Finding] = []
    for provider, items in _group_by_provider(txns).items():
        baseline = _baseline_rate_per_min(items, cfg)
        window = cfg.velocity_window_minutes
        flagged: set[str] = set()
        left = 0
        for right in range(len(items)):
            while (items[right]["ts"] - items[left]["ts"]).total_seconds() / 60.0 > window:
                left += 1
            win = items[left:right + 1]
            count = len(win)
            observed_rate = count / window
            mid_ts = win[len(win) // 2]["ts"]
            ev = active_event(mid_ts)
            eff_baseline = baseline * (cfg.velocity_event_multiplier if (ev and use_context) else 1.0)
            if count >= cfg.velocity_min_count and observed_rate >= eff_baseline * cfg.velocity_factor:
                flagged.update(t["id"] for t in win)

        if not flagged:
            continue
        cluster = [t for t in items if t["id"] in flagged]
        cluster.sort(key=lambda t: t["ts"])
        accounts = _distinct_accounts(cluster)
        span = max(1.0, _span_minutes(cluster))
        observed_rate = len(cluster) / span
        ev = active_event(cluster[-1]["ts"])
        findings.append(Finding(
            anomaly_type="velocity_spike",
            provider=provider,
            pool_id=provider,
            evidence=[
                f"{len(cluster)} transactions in {round(span)} minutes "
                f"(~{observed_rate:.1f}/min vs ~{baseline:.2f}/min normal)",
                f"concentrated in {len(accounts)} accounts",
                (f"rate far above even the raised {ev} baseline" if ev
                 else "sharp burst above the usual pace"),
            ],
            baseline={"txn_per_min": round(baseline, 2)},
            observed={"txn_per_min": round(observed_rate, 2), "transactions": len(cluster),
                      "distinct_accounts": len(accounts)},
            strength=min(1.0, 0.5 + 0.1 * min(5, observed_rate / max(baseline, 0.05))),
            covered_txn_ids=[t["id"] for t in cluster],
            ts=cluster[-1]["ts"],
            within_event=ev,
            accounts=accounts,
        ))
    return findings


# ------------------------------------------------------------------- off-hours
def _in_quiet_hours(ts: datetime, cfg: DetectorConfig) -> bool:
    return cfg.quiet_start_hour <= ts.hour < cfg.quiet_end_hour


def detect_off_hours(txns: list[Txn], cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG) -> list[Finding]:
    """High activity during typically-quiet hours with no known event to explain it."""
    findings: list[Finding] = []
    for provider, items in _group_by_provider(txns).items():
        quiet = [t for t in items if _in_quiet_hours(t["ts"], cfg) and active_event(t["ts"]) is None]
        if len(quiet) < cfg.off_hours_min_count:
            continue
        cluster = _densest_window(quiet, cfg.off_hours_window_minutes,
                                  cfg.off_hours_min_count, max_accounts=10_000)
        if not cluster:
            continue
        accounts = _distinct_accounts(cluster)
        findings.append(Finding(
            anomaly_type="off_hours_burst",
            provider=provider,
            pool_id=provider,
            evidence=[
                f"{len(cluster)} transactions between {_fmt_hm(cluster[0]['ts'])} "
                f"and {_fmt_hm(cluster[-1]['ts'])}",
                f"outside typical active hours ({cfg.quiet_start_hour:02d}:00–{cfg.quiet_end_hour:02d}:00)",
                "no known event (festival / salary day) to explain the activity",
            ],
            baseline={"expected_txns_in_quiet_hours": 0},
            observed={"transactions": len(cluster), "distinct_accounts": len(accounts)},
            strength=min(1.0, 0.5 + 0.06 * len(cluster)),
            covered_txn_ids=[t["id"] for t in cluster],
            ts=cluster[-1]["ts"],
            within_event=None,
            accounts=accounts,
        ))
    return findings


# --------------------------------------------------------- balance inconsistency
def detect_balance_inconsistency(
    pools: list[dict],
    net_by_pool: dict[str, int],
    cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG,
) -> list[Finding]:
    """Reported balance conflicts with balance computed from pool_effects.

    A data-quality anomaly. On a clean, consistent feed this yields nothing; it
    fires when a provider feed is late/missing/conflicting (Phase-5 break_feed).
    """
    findings: list[Finding] = []
    for pool in pools:
        pid = pool["pool_id"]
        computed = pool["opening_balance"] + net_by_pool.get(pid, 0)
        diff = pool["current_balance"] - computed
        if abs(diff) > cfg.balance_tolerance:
            findings.append(Finding(
                anomaly_type="balance_inconsistency",
                provider=pool.get("provider"),
                pool_id=pid,
                evidence=[
                    f"Reported balance {pool['current_balance']:,} BDT",
                    f"differs from balance computed from transactions ({computed:,} BDT)",
                    f"discrepancy of {abs(diff):,} BDT — feed may be late or inconsistent",
                ],
                baseline={"computed_balance": computed},
                observed={"reported_balance": pool["current_balance"], "discrepancy": diff},
                strength=0.7,
                covered_txn_ids=[],
                ts=pool.get("ts") or datetime.utcnow(),
                within_event=None,
            ))
    return findings
