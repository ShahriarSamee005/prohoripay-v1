# shared/contract.md — ProhoriPay API Contract

The single agreement between the backend and frontend sessions. Backend implements these shapes;
frontend builds its typed client and mock adapter against them. **Phase 0–1 shapes are final.**
Later-phase shapes are forward-declared so the frontend can plan, and are finalized in their phase.

---

## Conventions
- Base URL: `http://localhost:8000`. Frontend reads it from `NEXT_PUBLIC_API_BASE_URL`.
- All money is **integer BDT** (no paisa). Amounts are always positive; direction lives in `delta`.
- Timestamps are ISO-8601 UTC strings, e.g. `2026-07-11T09:14:00Z`.
- IDs are strings: `AGENT_07`, `txn_00001`, `ACC_1034`, `alert_0007`, `case_0003`.
- Responses that carry analytics include a `meta` object (see **Degraded-data convention**).

## Core enums
- `PoolId`: `physical_cash` | `bkash` | `nagad` | `rocket`
- `Provider` (e-money rails only): `bkash` | `nagad` | `rocket`
- `TxnType`: `cash_in` | `cash_out`
- `TxnStatus`: `completed` | `pending` | `failed`
- `PoolStatus`: `healthy` | `watch` | `critical`

---

## Data models

### Agent
```json
{ "id": "AGENT_07", "name": "Karim Store", "area": "Sylhet-Zindabazar",
  "providers": ["bkash", "nagad", "rocket"] }
```

### Pool
`physical_cash` is the single shared pool (kind `physical_cash`, provider `null`). Each provider has
one `provider_emoney` pool.
```json
{ "pool_id": "physical_cash", "kind": "physical_cash", "provider": null,
  "label": "Physical Cash", "balance": 80000, "currency": "BDT", "status": "critical" }
```

### Transaction (direction-aware — this encodes the core domain rule)
`pool_effects` is the source of truth for how balances move. `cash_out` drains physical cash and
credits provider e-money; `cash_in` is the reverse. Never reduce a balance without a signed effect.
```json
{ "id": "txn_00001", "ts": "2026-07-11T09:14:00Z", "provider": "bkash",
  "txn_type": "cash_out", "amount": 9500, "status": "completed",
  "account_id": "ACC_1034", "area": "Sylhet-Zindabazar", "event_flag": "eid_rush",
  "pool_effects": [ { "pool_id": "physical_cash", "delta": -9500 },
                    { "pool_id": "bkash", "delta": 9500 } ] }
```
> Ground-truth anomaly labels (`is_injected_anomaly`) are stored server-side for validation ONLY and
> are **never** returned by these endpoints — detection must earn its results.

---

## Phase 0 endpoints (final)
- `GET /health` → `{ "status": "ok", "time": "2026-07-11T09:14:00Z" }`

## Phase 1 endpoints (final)
- `GET /api/agent` → `Agent`
- `GET /api/pools` → `{ "pools": [Pool, ...], "meta": Meta }`
- `GET /api/transactions?limit=50&provider=bkash` →
  `{ "transactions": [Transaction, ...], "meta": Meta }` (`provider` optional; default limit 50)

## Degraded-data convention (used from Phase 1 onward)
Every analytics-bearing response includes:
```json
"meta": { "generated_at": "2026-07-11T09:14:00Z",
          "data_quality": "ok", "confidence_modifier": 1.0 }
```
- `data_quality`: `ok` | `degraded` | `stale`. When a provider feed is late/missing/conflicting,
  it is `degraded`/`stale` and `confidence_modifier` drops below `1.0`.
- The frontend **must** visibly lower confidence and show a caution when `data_quality != "ok"`.
  Never present a confident conclusion on degraded data (Scenario C).

---

## Forward-declared (finalized in the noted phase — shapes may refine)

### Phase 2 — Liquidity forecast
`GET /api/forecast` → `{ "forecasts": [Forecast, ...], "meta": Meta }`
```json
{ "pool_id": "bkash", "current_balance": 20000, "burn_rate_per_min": 2000,
  "minutes_to_depletion": 10, "projected_depletion_ts": "2026-07-11T09:24:00Z",
  "confidence": 0.92, "recommended_action": "Top up bKash via approved channel",
  "evidence": ["cash-out rate 2000/min over last 15m", "balance fell 30k→20k in 5m"] }
```

## Phase 3 endpoint (final) — Anomaly + liquidity alerts
Alerts come from TWO deterministic sources (no LLM): liquidity alerts derived from Phase-2 forecasts
(pool status critical/watch), and anomaly alerts from context-aware detection over transactions.
`GET /api/alerts` → `{ "alerts": [Alert, ...], "context": Context | null, "meta": Meta }`
Alerts are persisted with stable IDs (so Phase 4 can attach a case). Ordered by `ts` desc.
```json
{ "id": "alert_0007",
  "type": "anomaly",                 // "liquidity" | "anomaly"
  "severity": "high",                // "low" | "medium" | "high"
  "label": "unusual — requires review",   // liquidity: "liquidity pressure — requires attention"
  "anomaly_type": "structuring",     // null for liquidity; else structuring | velocity_spike |
                                     //   off_hours_burst | balance_inconsistency (detector's guess)
  "provider": "bkash",               // null allowed (e.g. physical_cash liquidity alert)
  "pool_id": "bkash",
  "evidence": ["12 transactions of ~9,500 BDT", "from 3 accounts", "within 45 min"],
  "baseline": { "txn_per_min": 2 }, "observed": { "txn_per_min": 15 },
  "confidence": 0.83,
  "ts": "2026-07-11T09:14:00Z",
  "case_id": null }                  // null until Phase 4 creates a case
```
`Context` (optional, powers the false-positive proof): when a known event explains high volume,
`{ "active_event": "eid_rush", "note": "high volume recognized as expected demand" }`. Language stays
safe throughout — never "fraud"/"suspicious".

### Phase 4 — Coordination / case lifecycle
`GET /api/cases`, `GET /api/cases/{id}`, and transition endpoints
`POST /api/cases/{id}/ack | /escalate | /resolve`.
```json
{ "id": "case_0003", "alert_id": "alert_0007", "provider": "bkash",
  "owner_role": "risk_reviewer", "status": "acknowledged", "escalation_level": 1,
  "next_step": "Review repeated-amount cluster", "opened_ts": "...",
  "history": [ { "stage": "raised", "actor": "system", "ts": "...", "detail": "..." } ] }
```
Routing: `liquidity → field_officer`, `anomaly → risk_reviewer`, `escalation → supervisor`.
`status`: `raised` | `routed` | `acknowledged` | `escalated` | `resolved`.

### Phase 5 — Live flow (SSE) + demo controls
`GET /api/stream` (SSE). Event `type`s: `balance_update` | `alert_new` | `case_update` | `feed_status`.
Demo controls: `POST /api/sim/eid_rush`, `POST /api/sim/inject_anomaly`, `POST /api/sim/break_feed`
(each returns `{ "ok": true }` and drives the stream).

### Phase 6 — Groq explanation
`POST /api/explain` body `{ "kind": "forecast|alert", "payload": {...}, "lang": "en|bn|banglish" }`
→ `{ "text": "...", "lang": "bn", "source": "groq|fallback" }`.

---

## Hero framing (UI contract for the main card)
The hero shows a prominent "**Total Holdings**" number, but it MUST: (a) be labeled as a sum of
separate, non-interchangeable pools; (b) show the **constraining pool** (lowest headroom / soonest
depletion) and an operational-status chip beside it; (c) never be presented as a single spendable
balance or the health signal. Health is per-pool. The breakdown (physical cash + each provider with
its logo) sits directly beneath, then the provider card row (each links to a provider detail screen).
