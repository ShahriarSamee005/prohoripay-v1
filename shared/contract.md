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

## Phase 2 endpoint (final) — Liquidity forecast
Deterministic per-pool projection. NO LLM. One Forecast per pool (all 4).
GET /api/forecast → { "forecasts": [Forecast, ...], "meta": Meta }
{ "pool_id": "bkash",
  "current_balance": 20000,
  "safety_floor": 5000,
  "burn_rate_per_min": 2000,
  "trend": "accelerating",
  "projection_state": "projected",   // projected | filling | insufficient_data | intermittent
  "minutes_to_depletion": 10,
  "projected_depletion_ts": "2026-07-11T09:24:00Z",
  "confidence": 0.92,
  "confidence_factors": { "volatility": "low", "sample_size": 42, "data_freshness": "ok" },
  "status": "critical",
  "recommended_action": "Top up bKash via approved channel",
  "evidence": ["cash-out rate 2000/min over last 15m", "balance fell 30k→20k in 5m"],
  "history": [ { "ts": "...", "balance": 30000 }, { "ts": "...", "balance": 20000 } ] }

Field rules:
- burn_rate_per_min = net signed EMA of pool_effects over the recent window (recency-weighted, NOT a
  flat average). Positive = draining, negative = filling.
- trend: accelerating | steady | easing | filling. May escalate to "accelerating" ONLY when the
  consecutive-increase gate passes AND the jump is not dominated by a single transaction.
- projection_state disambiguates a null countdown: filling = safe (growing); insufficient_data
  and intermittent = LOW-CONFIDENCE, actively watching (NOT "all clear"); projected = a real
  countdown is present. minutes_to_depletion is non-null only when projected.
- minutes_to_depletion / projected_depletion_ts are null unless projection_state == "projected".
- status derived from minutes_to_depletion (config: <30 critical, <90 watch, else healthy; any
  non-projected state => not critical by projection). /api/pools reports this SAME status.
- confidence earned from volatility + sample size + meta.confidence_modifier (freshness). Reduced in
  insufficient_data / intermittent / degraded-feed states.
- recommended_action: advisory, provider-respecting, safe language (never "transfer from X").
- history: short recent balance series for the burn-down chart; projection line runs from the last
  point to (projected_depletion_ts, safety_floor).

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

## Phase 4 endpoint (final) — Coordination / case lifecycle
When an alert is raised, a Case is auto-created and routed by type. Cases carry an immutable audit
history and support human transitions. NOTHING here executes a financial action — it notifies,
assigns, acknowledges, escalates, recommends, and tracks. Every transition is actor-attributed.

Routing by alert type: `liquidity → field_officer`, `anomaly → risk_reviewer`; escalation raises to
`supervisor` then `area_manager` (configurable ladder).

`GET /api/cases?status=&provider=` → `{ "cases": [Case, ...], "meta": Meta }`
`GET /api/cases/{id}` → `Case`
`POST /api/cases/{id}/ack`      body `{ "actor": "field_officer", "note": "" }` → `Case`
`POST /api/cases/{id}/escalate` body `{ "actor": "field_officer", "note": "" }` → `Case`
`POST /api/cases/{id}/resolve`  body `{ "actor": "risk_reviewer", "note": "reviewed — salary payment" }` → `Case`
```json
{ "id": "case_0003",
  "alert_id": "alert_0007",
  "type": "anomaly",                 // mirrors the alert type
  "provider": "bkash",               // null allowed
  "owner_role": "risk_reviewer",     // field_officer | risk_reviewer | supervisor | area_manager
  "status": "acknowledged",          // raised | routed | acknowledged | escalated | resolved
  "escalation_level": 0,             // 0 base; +1 per escalation up the ladder
  "next_step": "Review repeated-amount cluster",
  "recommended_action": "Review the 12 near-identical transfers with the agent before any action",
  "opened_ts": "2026-07-11T09:14:00Z",
  "updated_ts": "2026-07-11T09:20:00Z",
  "sla_minutes": 30,                 // time budget before auto-escalation is due
  "history": [                       // immutable, append-only audit trail
    { "stage": "raised",        "actor": "system",        "ts": "...", "detail": "auto-created from alert_0007" },
    { "stage": "routed",        "actor": "system",        "ts": "...", "detail": "routed to risk_reviewer" },
    { "stage": "acknowledged",  "actor": "risk_reviewer", "ts": "...", "detail": "" }
  ] }
```
Transitions are guarded: illegal moves (e.g. resolve before ack, or acting on a resolved case) return
`409` with a safe message. Valid transitions append a history entry and update status/owner. On the
Alert, `case_id` is now populated. Auto-escalation is time-based (see Phase 5 clock); the fields
(`sla_minutes`, `escalation_level`) are wired now and driven live in Phase 5.

## Phase 5 endpoints (final) — Live flow (SSE) + demo controls
A simulation clock advances synthetic time in ticks, applies transactions, re-runs forecast +
detection + escalation, and pushes changes over SSE. Demo controls let the presenter drive scenarios
live. Still advisory only; controls generate synthetic events, never real actions.

### SSE stream
`GET /api/stream` (text/event-stream). Each message: `event: <type>` + `data: <json>`.
Event types and payloads:
- `tick`          `{ "sim_time": "2026-07-11T09:20:00Z", "tick": 42 }`
- `balance_update``{ "pools": [Pool, ...], "meta": Meta }`            // same shapes as /api/pools
- `forecast_update` `{ "forecasts": [Forecast, ...], "meta": Meta }` // same as /api/forecast
- `alert_new`     `{ "alert": Alert }`                               // a newly raised alert
- `case_update`   `{ "case": Case }`                                 // created or transitioned
- `feed_status`   `{ "provider": "bkash", "data_quality": "stale", "confidence_modifier": 0.4 }`
Client should treat these as authoritative refreshes for the affected slice. On reconnect, client may
re-fetch REST snapshots then resume the stream.

### Simulation controls (presenter-driven; each returns `{ "ok": true, "applied": "<summary>" }`)
- `POST /api/sim/start`  body `{ "speed": 1 }`      // begin/resume the clock (speed = ticks/sec)
- `POST /api/sim/pause`                              // pause the clock
- `POST /api/sim/reset`                              // reseed to the initial scenario
- `POST /api/sim/eid_rush`   body `{ "provider": "physical_cash", "intensity": "high" }`
      // inject sustained cash-out pressure → drives a liquidity alert (Scenario A)
- `POST /api/sim/inject_anomaly` body `{ "provider": "bkash", "type": "structuring" }`
      // inject a labeled anomaly cluster → drives an anomaly alert + case
- `POST /api/sim/break_feed` body `{ "provider": "nagad", "mode": "stale" }`
      // mark a provider feed stale/late → data_quality degrades, confidence drops (Scenario C)
- `POST /api/sim/restore_feed` body `{ "provider": "nagad" }`   // clear the degraded state

Degraded feeds MUST propagate: affected forecasts/alerts carry `meta.data_quality != "ok"` and a
reduced `confidence_modifier`; the sim also emits a `feed_status` event. Auto-escalation
(`evaluate_escalations`) runs on each tick against sim_time.

## Phase 6 endpoint (final) — Natural-language explanation (Groq)
The LLM ONLY translates already-computed structured results into human-readable text. It never
calculates, detects, scores, or decides. Backend loads the AUTHORITATIVE structured object by id
(not client-supplied numbers), feeds it to Groq under strict constraints, then runs a safety guard;
on any Groq error/timeout OR a guard failure it returns a deterministic TEMPLATE fallback. Results are
cached by (kind, id, lang, data-hash) so they're instant and stable during the demo.

POST /api/explain
body { "kind": "forecast" | "alert", "id": "<pool_id or alert_id>", "lang": "en" | "bn" | "banglish" }
→
{ "text": "bKash balance has been falling steadily; at the current cash-out rate it may run low in
           about 10 minutes. Consider topping up via the approved channel. Human review recommended.",
  "lang": "en",
  "source": "groq",            // "groq" | "fallback"
  "kind": "forecast",
  "id": "bkash" }
Constraints the model MUST obey (enforced by prompt + post-check): explain only the provided facts;
invent no numbers; never the words "fraud"/"suspicious"/"criminal"; advisory, provider-respecting
language; 2–4 sentences; end with a human-review note for high-impact items. Any violation ⇒ fallback.
---

## Hero framing (UI contract for the main card)
The hero shows a prominent "**Total Holdings**" number, but it MUST: (a) be labeled as a sum of
separate, non-interchangeable pools; (b) show the **constraining pool** (lowest headroom / soonest
depletion) and an operational-status chip beside it; (c) never be presented as a single spendable
balance or the health signal. Health is per-pool. The breakdown (physical cash + each provider with
its logo) sits directly beneath, then the provider card row (each links to a provider detail screen).
