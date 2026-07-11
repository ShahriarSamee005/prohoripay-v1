Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 3 alerts now final), and ./shared/dos.md +
./shared/our_idea.md (feature #3 explainable evidence, #6 context-aware spikes). Work ONLY inside
./backend. Phase 2 is complete and committed.

PHASE 3 GOAL: deterministic, context-aware anomaly detection with human-readable evidence, PLUS
liquidity alerts derived from Phase-2 forecasts, persisted and served via /api/alerts — measured
against the injected ground-truth labels. NO LLM anywhere in detection.

DETECTION MODULE (app/modules/alerts/, deterministic; rules primary, IsolationForest optional):
- Detect at least these anomaly_types over the seeded transactions, each producing EVIDENCE strings
  (never a bare score):
  * structuring: many near-identical amounts from a small account cluster in a short window.
  * velocity_spike: txn/min far above the pool's baseline.
  * off_hours_burst: high activity in typically-quiet hours.
  * balance_inconsistency: reported balance conflicts with balance computed from pool_effects
    (this is a data-quality anomaly).
- CONTEXT-AWARE BASELINE (the false-positive control — critical): cross-reference a known-event
  calendar (eid_rush, salary_day) from event_flag / a small config calendar BEFORE flagging pure
  volume. During a known event, raise the baseline / suppress volume-only flags so a NORMAL Eid surge
  is classified as EXPECTED DEMAND and NOT flagged. When suppressed by context, populate the response
  `context` object. Do NOT use a static threshold.
- Optional: an IsolationForest as a secondary ensemble signal on features (amount, inter-arrival,
  account frequency). It may only RAISE confidence on an already-evidenced rule hit — it must never be
  the sole justification, and every alert still carries plain-language evidence.
- Each anomaly alert: label "unusual — requires review", anomaly_type, provider/pool, evidence[],
  baseline{}, observed{}, confidence (earned: strength of deviation x context x data freshness).

LIQUIDITY ALERTS (from Phase-2 forecasts):
- For pools with status critical (and watch, configurable), emit a type:"liquidity" alert:
  label "liquidity pressure — requires attention", evidence + baseline/observed from the forecast,
  confidence = forecast confidence, provider = pool's provider (null for physical_cash).

PERSISTENCE + ENDPOINT:
- Persist alerts to an alerts table with stable IDs (case_id null for now). A run_detection() populates
  them over seeded history + current forecasts (call on seed/startup).
- GET /api/alerts -> { alerts:[...] ordered by ts desc, context, meta }.

TESTS (tests/) — these produce our required metrics:
- PRECISION / RECALL / F1 at the anomaly-cluster level: compare detected anomaly alerts against the
  server-side is_injected_anomaly / anomaly_type ground truth (an injected cluster counts as detected
  if an alert covers its transactions). Print precision, recall, F1.
- FALSE-POSITIVE RATE: run detection over the NORMAL control traffic (event_flag eid_rush /salary_day
  where is_injected_anomaly is false). Assert the normal Eid/salary surge is NOT flagged; print
  FP rate. This is the headline "we didn't cry wolf on Eid" proof.
- Safe-language test: assert no alert label/evidence contains "fraud"/"suspicious"/"criminal".
- Ground-truth leak test: assert is_injected_anomaly / anomaly_type never appear in /api/alerts JSON.
- Endpoint shape matches contract (alerts + context + meta).

TEST GATE: pytest green; GET /api/alerts returns anomaly + liquidity alerts with evidence; the
normal-Eid control is NOT flagged. Paste pytest output + sample /api/alerts response + the printed
precision/recall/F1 and FP-rate numbers, then STOP. Do not start Phase 4.

Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 3 alerts final), ./shared/design.md, and
./shared/our_idea.md (#3 evidence, #7 inclusive Bangla comms). Work ONLY inside ./frontend. Phase 2
is complete and committed.

PHASE 3 GOAL: an alert feed that lives INSIDE the connected dashboard (not a separate tab), showing
evidence-first alerts with per-alert confidence, safe language, and at least one Bangla/Banglish
alert — plus the "recognized as Eid demand" context proof.

API + MOCK:
- Extend lib/api.ts with getAlerts() and the Alert + Context types. Extend the mock with a mix:
  a structuring anomaly (high severity, full evidence), a velocity_spike, a physical_cash liquidity
  alert (critical), and a Context object indicating Eid demand recognized as expected.

ALERT FEED (a section of the main dashboard, reinforcing the connected story — NOT a standalone page):
- Each alert card shows: type badge (liquidity vs anomaly), severity color (status colors only),
  the SAFE label, anomaly_type (if any), provider/pool, timestamp, and CONFIDENCE beside that alert
  (not global).
- EVIDENCE-FIRST: render the evidence[] list prominently and a compact baseline-vs-observed
  comparison (e.g. "normal 2/min → observed 15/min"). NEVER show a bare score as justification.
- BANGLA/BANGLISH: at least one alert renders a Bangla (or Banglish) line via a language toggle on the
  card (static templates for now; Groq wires in Phase 6). Example tone:
  "⚠️ bKash-এ অস্বাভাবিক লেনদেন — রিভিউ প্রয়োজন।"
- CONTEXT CHIP: when context.active_event is set, show a calm informational chip on the dashboard
  ("High volume recognized as Eid demand — treated as expected") to visibly prove the false-positive
  control. Different visual weight from a real alert (informational, not warning).
- Clicking an alert opens a detail drawer/panel: full evidence, baseline vs observed,
  confidence_factors, recommended context. Leave a clearly-marked "Coordination" placeholder in the
  drawer (Phase 4 adds owner/ack/escalate/resolve here).
- All money tabular-nums; magenta accent; language stays safe.

SWAP + TEST GATE:
1. Build on mock; verify the feed, evidence, per-alert confidence, the Bangla toggle, and the Eid
   context chip all render.
2. With backend Phase 3 running, flip to live: the feed shows REAL anomaly + liquidity alerts with
   real evidence; the context chip reflects the live context; no alert shows a bare score.
3. Alert detail drawer opens with full evidence + confidence factors and the Coordination placeholder.
Confirm all three, paste any errors, then STOP. Do not start Phase 4.