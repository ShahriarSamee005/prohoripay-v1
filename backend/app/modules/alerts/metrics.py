"""Detection validation metrics (required deliverables): precision / recall / F1
and the false-positive rate against the server-side ground-truth labels.

An injected cluster counts as DETECTED if an anomaly alert covers a sufficient
fraction of its transactions. An alert is a TRUE POSITIVE if the majority of the
transactions it covers are genuinely injected.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.models import Alert, Transaction
from app.modules.alerts.config import MATCH_FRACTION


def _ground_truth_clusters(session: Session) -> dict[str, set[str]]:
    """Injected transactions grouped by anomaly_type -> set of txn ids."""
    clusters: dict[str, set[str]] = {}
    for t in session.exec(select(Transaction).where(Transaction.is_injected_anomaly == True)).all():  # noqa: E712
        clusters.setdefault(t.anomaly_type, set()).add(t.id)
    return clusters


def evaluate_detection(session: Session) -> dict:
    """Cluster-level precision / recall / F1 of anomaly detection vs ground truth."""
    gt = _ground_truth_clusters(session)
    injected_ids = {tid for ids in gt.values() for tid in ids}

    anomaly_alerts = session.exec(
        select(Alert).where(Alert.type == "anomaly")
    ).all()

    # Precision: an alert is a TP if most of what it covers is genuinely injected.
    tp = fp = 0
    for a in anomaly_alerts:
        covered = set(a.covered_txn_ids)
        if not covered:
            # e.g. balance_inconsistency (no covered txns) — skip from precision.
            continue
        injected_frac = len(covered & injected_ids) / len(covered)
        if injected_frac >= MATCH_FRACTION:
            tp += 1
        else:
            fp += 1
    total_alerts = tp + fp
    precision = tp / total_alerts if total_alerts else 1.0

    # Recall: a GT cluster is detected if some alert covers >= MATCH_FRACTION of it.
    detected = 0
    per_cluster = {}
    for atype, ids in gt.items():
        best = 0.0
        for a in anomaly_alerts:
            overlap = len(set(a.covered_txn_ids) & ids) / len(ids)
            best = max(best, overlap)
        hit = best >= MATCH_FRACTION
        per_cluster[atype] = {"size": len(ids), "best_overlap": round(best, 2), "detected": hit}
        detected += int(hit)
    recall = detected / len(gt) if gt else 1.0

    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        "true_positive_alerts": tp, "false_positive_alerts": fp,
        "clusters_total": len(gt), "clusters_detected": detected,
        "per_cluster": per_cluster,
    }


def false_positive_rate(session: Session) -> dict:
    """Headline 'didn't cry wolf on Eid' proof.

    fp_rate = fraction of anomaly alerts that are false positives (majority of
    covered transactions are NON-injected). Zero means no legitimate surge was
    mistaken for an anomaly.
    """
    injected_ids = {
        t.id for t in session.exec(
            select(Transaction).where(Transaction.is_injected_anomaly == True)  # noqa: E712
        ).all()
    }
    anomaly_alerts = [a for a in session.exec(select(Alert).where(Alert.type == "anomaly")).all()
                      if a.covered_txn_ids]

    false_alerts = 0
    for a in anomaly_alerts:
        covered = set(a.covered_txn_ids)
        injected_frac = len(covered & injected_ids) / len(covered)
        if injected_frac < MATCH_FRACTION:
            false_alerts += 1
    total = len(anomaly_alerts)
    fp_rate = false_alerts / total if total else 0.0

    # How many genuinely-normal (Eid/salary) transactions were incidentally covered.
    normal_covered = 0
    normal_total = 0
    for t in session.exec(select(Transaction)).all():
        if t.is_injected_anomaly:
            continue
        if t.event_flag in ("eid_rush", "salary_day"):
            normal_total += 1
    covered_ids: set[str] = set()
    for a in anomaly_alerts:
        covered_ids.update(a.covered_txn_ids)
    for t in session.exec(select(Transaction)).all():
        if (not t.is_injected_anomaly and t.event_flag in ("eid_rush", "salary_day")
                and t.id in covered_ids):
            normal_covered += 1

    return {
        "false_positive_alerts": false_alerts,
        "total_anomaly_alerts": total,
        "fp_rate": round(fp_rate, 3),
        "normal_event_txns": normal_total,
        "normal_event_txns_incidentally_covered": normal_covered,
    }
