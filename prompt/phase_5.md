Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 5 SSE + sim controls now final), and
./shared/our_idea.md (#9 traceability, safe fallback). Work ONLY inside ./backend. Phase 4 is complete
and committed.

PHASE 5 GOAL: a simulation clock that advances synthetic time, applies transactions, re-runs
forecast + detection + escalation each tick, and streams changes over SSE — plus presenter-driven
sim controls including a break-feed path that degrades confidence (Scenario C). Still advisory only.

SIM MODULE (app/modules/sim/):
- A SimulationClock: an async task that on each tick advances sim_time, generates the next batch of
  synthetic transactions (reuse the Phase-1 generator, direction-aware), persists them, then re-runs:
  forecast recompute -> detection (new alerts) -> case auto-creation -> evaluate_escalations(sim_time).
- An in-memory pub/sub (asyncio.Queue per subscriber) that broadcasts events. On each tick emit:
  tick, then balance_update + forecast_update; emit alert_new for each newly raised alert; case_update
  for created/changed cases; feed_status when a feed's state changes.
- START PAUSED by default (deterministic demos). speed = ticks/sec is configurable.

SSE ENDPOINT:
- GET /api/stream (text/event-stream) using StreamingResponse. Register a subscriber queue, yield
  "event: <type>\ndata: <json>\n\n" per contract, send periodic keep-alive comments, and clean up the
  subscriber on disconnect. Handle multiple concurrent clients.

SIM CONTROLS (per contract, each returns {ok, applied}):
- POST /api/sim/start|pause|reset, /api/sim/eid_rush, /api/sim/inject_anomaly,
  /api/sim/break_feed, /api/sim/restore_feed.
- BREAK_FEED (Scenario C — critical): mark a provider's feed stale/late. While degraded, that
  provider's forecasts/alerts MUST set meta.data_quality != "ok" and a reduced confidence_modifier,
  and confidence values must actually drop (thread confidence_modifier through the confidence calc).
  Emit a feed_status event. restore_feed clears it. NEVER produce a confident conclusion on a degraded
  feed.
- inject_anomaly injects a labeled cluster that detection then catches on the next tick (end-to-end).
- eid_rush injects sustained cash-out pressure that drives a liquidity alert within a few ticks.

DETERMINISM + SAFETY:
- Fixed seeds so a given control sequence reproduces the same demo. Controls only generate SYNTHETIC
  events — no real/financial actions.

TESTS (tests/):
- Stream smoke: a subscriber receives tick + balance_update within N ticks after start.
- eid_rush -> a liquidity alert appears within a bounded number of ticks.
- inject_anomaly -> a matching anomaly alert + auto-created case appear.
- break_feed -> that provider's forecast confidence DROPS and meta.data_quality becomes stale; a
  feed_status event is emitted; restore_feed returns it to ok and confidence recovers.
- Auto-escalation fires on ticks once a case passes its SLA in sim_time.
- Multiple subscribers each receive broadcasts; disconnect cleans up without error.

TEST GATE: pytest green; with the server running, start the sim and confirm SSE emits ticks +
balance/forecast updates; each control produces its effect. Paste pytest output + a short captured
SSE snippet (a few events incl a feed_status after break_feed), then STOP. Do not start Phase 6.

Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 5 SSE + sim controls final), and
./shared/design.md. Work ONLY inside ./frontend. Phase 4 is complete and committed.

PHASE 5 GOAL: make the dashboard LIVE via SSE (balances, forecasts, alerts, cases update in real time)
and add a presenter Demo Control panel to drive the scenarios on stage — including a break-feed that
visibly drops confidence and shows a caution (Scenario C).

SSE CLIENT:
- lib/stream.ts: subscribe to GET /api/stream (EventSource or fetch-stream). Parse each event by type
  and update a central store (React context / Zustand / useReducer) so every widget re-renders from
  live data: balance_update -> pools/hero, forecast_update -> provider detail + statuses,
  alert_new -> alert feed (with a subtle Framer entrance), case_update -> case panel + active-cases
  strip, feed_status -> DataQualityBanner + confidence. Handle reconnect: re-fetch REST snapshots then
  resume. Show a small "LIVE" indicator + sim_time from tick.

LIVE BEHAVIOR:
- Balances/countdowns/statuses update smoothly as ticks arrive (animate number changes; keep
  tabular-nums so digits don't jitter). No full-page reloads.
- New alerts animate into the feed; new/updated cases reflect in the case panel + active-cases strip
  in real time.
- On feed_status stale/degraded: the DataQualityBanner shows a clear caution for that provider AND the
  affected confidence values visibly drop (the number, not just a banner). This is the Scenario C proof.

DEMO CONTROL PANEL (presenter tool — a side panel or drawer, clearly a demo aid):
- Buttons: Start / Pause / Reset; Trigger Eid Rush; Inject Anomaly (provider + type); Break Feed
  (provider) / Restore Feed. Each POSTs the matching /api/sim/* endpoint.
- Show the current sim clock + a compact event log ("09:20 — liquidity alert raised: physical cash")
  so the audience can follow what each button caused.
- Style it as an operator/presenter control (distinct from the real dashboard), safe language only.

TEST GATE:
1. With backend Phase 5 running, Start the sim: balances/forecasts/statuses update live over SSE with
   a visible LIVE indicator and moving sim_time; no reloads.
2. Trigger Eid Rush -> a liquidity alert animates into the feed and its case appears. Inject Anomaly ->
   an anomaly alert + case appear and are drivable through the Phase-4 lifecycle live.
3. Break Feed on one provider -> DataQualityBanner caution shows AND that provider's confidence
   visibly drops; Restore Feed clears it and confidence recovers.
Confirm all three, paste any errors, then STOP. Do not start Phase 6.