"""Detection validation metrics — the required deliverables (printed for the gate).

Precision / Recall / F1 at the anomaly-cluster level against the injected
ground truth, and the headline false-positive rate on the normal Eid control.
"""

from __future__ import annotations

from app.modules.alerts.metrics import evaluate_detection, false_positive_rate


def test_precision_recall_f1(db_session, capsys):
    m = evaluate_detection(db_session)

    # Every injected cluster is detected, with no false-positive alerts.
    assert m["clusters_detected"] == m["clusters_total"] == 3
    assert m["false_positive_alerts"] == 0
    assert m["recall"] == 1.0
    assert m["precision"] == 1.0
    assert m["f1"] == 1.0

    with capsys.disabled():
        print(
            f"\n[METRIC] Detection precision={m['precision']} recall={m['recall']} "
            f"F1={m['f1']} (TP={m['true_positive_alerts']}, FP={m['false_positive_alerts']}, "
            f"clusters {m['clusters_detected']}/{m['clusters_total']})"
        )
        for atype, c in m["per_cluster"].items():
            print(f"           - {atype}: {c['size']} txns, overlap {c['best_overlap']}, "
                  f"detected={c['detected']}")


def test_false_positive_rate_on_normal_eid(db_session, capsys):
    fp = false_positive_rate(db_session)

    # The normal Eid surge is NOT flagged — no false alarms.
    assert fp["fp_rate"] == 0.0
    assert fp["false_positive_alerts"] == 0
    assert fp["normal_event_txns"] > 0
    assert fp["normal_event_txns_incidentally_covered"] == 0

    with capsys.disabled():
        print(
            f"\n[METRIC] False-positive rate = {fp['fp_rate']} "
            f"({fp['false_positive_alerts']}/{fp['total_anomaly_alerts']} alerts); "
            f"{fp['normal_event_txns_incidentally_covered']}/{fp['normal_event_txns']} "
            f"normal Eid transactions incorrectly covered — did NOT cry wolf on Eid."
        )
