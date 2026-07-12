# ProhoriPay — Validation & Metrics

All metrics are measured against the deterministic synthetic dataset produced by `python -m app.core.seed` (seed 1, reference date 2026-07-11). The dataset is fully reproducible: the same seed produces the same transactions, the same injected anomalies, and the same balances every time.

---

## Ground Truth

**39 injected, labeled anomaly transactions** are embedded in the seeded history across three clusters. Their labels (`is_injected_anomaly=True`, `anomaly_type`) are stored server-side in the `Transaction` table and are **never returned by any public API endpoint** — the detection engine must earn its results independently. The labels exist only for:

1. Validation queries (precision / recall measurement below).
2. The seed summary printout (`python -m app.core.seed`).
3. Integration tests that assert labels are present in the DB but absent from all API responses.

| Cluster | Type | Provider | Count | Time window | Notes |
|---|---|---|---|---|---|
| A | `structuring` | bKash | 12 | 11:00–11:45 (inside Eid rush) | 3 accounts, amounts 4,910–4,990 BDT |
| B | `velocity_spike` | Rocket | 18 | 11:30–11:36 (inside Eid rush) | 2 accounts, amounts 1,000–3,000 BDT |
| C | `off_hours_burst` | Nagad | 9 | 03:05–03:35 (off-hours) | 2 accounts, amounts 2,000–4,000 BDT |

Clusters A and B are deliberately placed inside the Eid-rush window (10:00–12:00) to verify the Eid-aware baseline prevents the surrounding ~70 legitimate Eid-rush transactions from absorbing or masking them.

---

## Metric 1: Shortage Detection Lead Time

**Definition:** How many minutes before physical cash reaches its safety floor (10,000 BDT) does the system first raise a `liquidity` alert with `severity = "critical"` for `physical_cash`?

**How to measure:**

1. Run `python -m app.core.seed` to produce the standard seeded state.
2. Call `GET /api/forecast` and read `projected_depletion_ts` for `pool_id = "physical_cash"`.
3. Call `GET /api/alerts` and find the earliest `liquidity` alert with `pool_id = "physical_cash"` and `severity = "critical"`. Read its `ts`.
4. **Lead time = `projected_depletion_ts − alert.ts` in minutes.**

Alternatively, measure dynamically by running the simulation: `POST /api/sim/start` then `POST /api/sim/eid_rush`. Watch the first `alert_new` SSE event for `physical_cash` and compare it to the `minutes_to_depletion` in the concurrent `forecast_update` event.

The forecast engine raises a `critical` alert when `minutes_to_depletion < 30` (configured as `ForecastConfig.critical_minutes = 30.0` in `backend/app/modules/forecast/config.py`). In the standard seeded state, physical cash is already constrained by the Eid-rush history; the lead time measures how far ahead this constraint is surfaced.

| Metric | Value |
|---|---|
| Shortage detection lead time (seeded scenario) | `<FILL: X minutes>` |

---

## Metric 2: Anomaly Detection — Precision, Recall, F1

**Definitions:**

- **True positive (TP):** An anomaly alert whose covered transaction IDs overlap ≥ 50% with an injected cluster (`MATCH_FRACTION = 0.5` from `backend/app/modules/alerts/config.py`).
- **False positive (FP):** An anomaly alert whose covered transactions are entirely non-injected.
- **False negative (FN):** An injected cluster that is not covered by any anomaly alert above the overlap threshold.
- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN) where total positives = 3 clusters
- **F1** = 2 × Precision × Recall / (Precision + Recall)

**How to measure:**

1. Run `python -m app.core.seed`.
2. Call `GET /api/alerts` and filter for `type = "anomaly"`.
3. For each alert, retrieve the `covered_txn_ids` (present in the alert response).
4. Query the database directly (not via API — labels are never in API responses): for each `txn_id` in `covered_txn_ids`, look up `is_injected_anomaly` in the `transaction` table.
5. Apply the 50% overlap rule per alert vs each injected cluster to classify TP, FP, FN.

**Important:** The IsolationForest secondary signal (`isolation_forest_enabled = True`, `contamination = 0.12`, `random_state = 0`) can *raise* confidence on an already-evidenced finding by `isolation_forest_confidence_bump = 0.05`, but it **never creates a finding on its own**. Precision and recall are driven entirely by the primary rule detectors.

| Metric | Value |
|---|---|
| True positives (clusters correctly detected) | `<FILL: X / 3>` |
| False positives (alerts on non-injected traffic) | `<FILL: X>` |
| False negatives (injected clusters missed) | `<FILL: X>` |
| **Precision** | `<FILL: X%>` |
| **Recall** | `<FILL: X%>` |
| **F1 score** | `<FILL: X.XX>` |

---

## Metric 3: False-Positive Rate on Normal Eid / Salary Traffic

**Definition:** The fraction of non-injected Eid-rush transactions that appear in the `covered_txn_ids` of any anomaly alert.

This is the key Eid-awareness measure. Clusters A and B are injected inside the Eid window (10:00–12:00); the 70 Eid-rush transactions in the seeded dataset are the non-injected population. The detector must distinguish the injected clusters from the surrounding legitimate volume.

**How to measure:**

1. Run `python -m app.core.seed`.
2. Query the database: select all `transaction` rows where `event_flag = 'eid_rush'` AND `is_injected_anomaly = false`. This gives the non-injected Eid-rush population (approximately 58 transactions — 70 Eid-rush total minus the 12 injected structuring transactions that overlap the same window; exact count varies slightly by RNG path).
3. Collect all `covered_txn_ids` from anomaly alerts in `GET /api/alerts`.
4. Count how many non-injected Eid-rush transaction IDs appear in any alert's coverage.
5. **FP rate = (non-injected Eid transactions covered by any alert) / (total non-injected Eid transactions)**

**Design targets:** The context-aware velocity detector raises its baseline by `velocity_event_multiplier = 2.0×` during the Eid window (10:00–12:00), and the observed rate must then exceed `velocity_factor = 4.0×` the raised baseline to fire. Normal Eid-rush volume in the seeded dataset is designed to stay below this. The structuring detector is amount-cluster-based and not triggered by varied amounts from many distinct accounts.

| Metric | Value |
|---|---|
| Non-injected Eid-rush transactions in scope | `<FILL: ~58>` |
| Covered by an anomaly alert | `<FILL: X>` |
| **False-positive rate** | `<FILL: X%>` |

---

## Metric 4: API Latency P95

**How to measure:**

1. Run `python -m app.core.seed` to produce the standard seeded state (~135 transactions, 4 pools, ~6 alerts).
2. Start the server: `uvicorn app.main:app --port 8000` (no `--reload`).
3. Warm up with 10 requests, then send 100 sequential requests to each endpoint.
4. Record each response time; compute the 95th percentile.

```python
import httpx, statistics, time

BASE = "http://localhost:8000"
for path in ["/api/forecast", "/api/alerts", "/api/pools"]:
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        httpx.get(BASE + path)
        latencies.append((time.perf_counter() - t0) * 1000)
    p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
    print(f"{path}: P95 = {p95:.1f} ms")
```

**Data volume at measurement time:** ~135 seeded transactions, 4 pools, ~6 alerts. These are the values that determine the analytics computation cost.

**Note on `/api/explain`:** The Groq path is network-bound (target < 8 seconds, `groq_timeout_seconds = 8.0`, `groq_max_retries = 1` from `backend/app/core/config.py`). The deterministic fallback path is fully local and expected to return in < 5 ms.

| Endpoint | P50 | P95 | Notes |
|---|---|---|---|
| `GET /api/forecast` | `<FILL: X ms>` | `<FILL: X ms>` | EMA over 30-min window, all 4 pools |
| `GET /api/alerts` | `<FILL: X ms>` | `<FILL: X ms>` | 4 rule detectors + liquidity checks |
| `GET /api/pools` | `<FILL: X ms>` | `<FILL: X ms>` | Simple read + forecast-derived status |
| `POST /api/explain` (Groq) | `<FILL: X ms>` | `<FILL: X ms>` | Network-bound to Groq API |
| `POST /api/explain` (fallback) | `<FILL: X ms>` | `<FILL: X ms>` | Fully local, no Groq call |

---

## Summary Table

| Metric | Value | Source |
|---|---|---|
| Shortage detection lead time | `<FILL: X min>` | `projected_depletion_ts − first_critical_alert.ts` |
| Anomaly precision | `<FILL: X%>` | TP / (TP + FP), 50% cluster overlap threshold |
| Anomaly recall | `<FILL: X%>` | TP / 3 injected clusters |
| Anomaly F1 | `<FILL: X.XX>` | Harmonic mean |
| FP rate (normal Eid traffic) | `<FILL: X%>` | Non-injected Eid txns in anomaly alert scope |
| API latency P95 — `/api/forecast` | `<FILL: X ms>` | 100 requests, seeded DB, no reload |
| API latency P95 — `/api/alerts` | `<FILL: X ms>` | 100 requests, seeded DB, no reload |

---

## What These Numbers Do and Do Not Claim

**What they show:** The detection method works on known synthetic patterns in a controlled, reproducible scenario. Given the labeled ground truth, we can measure whether the three detectors fire on the three clusters and whether they hold off on the surrounding legitimate traffic. The fixed seed ensures anyone can reproduce these results.

**What they do not show:**
- **Generalization to unseen patterns.** The detectors were designed with knowledge of the three anomaly types. They have not been tested on held-out anomaly types.
- **Production accuracy.** Real MFS traffic has distribution shift, adversarial behavior, data quality problems, and volume characteristics that a 3-hour synthetic scenario cannot represent.
- **Multi-agent performance.** The seeded dataset covers one agent. Detection accuracy on a multi-agent fleet with inter-agent coordination patterns is undefined.
- **Latency under production load.** SQLite is single-writer. P95 latency under real concurrent load would be different.

These metrics demonstrate the *approach* is measurable and the *method* is sound. They are not production accuracy claims.
