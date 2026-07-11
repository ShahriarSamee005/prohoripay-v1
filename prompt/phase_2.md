##backend

Read ./CLAUDE.md and the UPDATED ./shared/contract.md (Phase 2 forecast is now final). Work ONLY
inside ./backend. Phase 1 is complete and committed.

PHASE 2 GOAL: a deterministic per-pool liquidity forecast module (NO LLM) that matches the finalized
Forecast shape exactly, and make pool status forecast-driven. New module; keep main.py thin.

FORECAST ENGINE (app/modules/forecast/, deterministic pandas/numpy):
- For each of the 4 pools independently, compute from the signed pool_effects of recent transactions:
  * net_burn_rate = EMA (recency-weighted, NOT flat average) of net signed flow per minute over a
    configurable recent window. Positive = draining, negative = filling.
  * TREND-AWARE (light): split the window into an earlier and a more-recent sub-window; compute each
    sub-window's net rate. recent meaningfully > earlier => trend "accelerating" and use the higher
    recent rate as the projection rate (countdown shortens); recent < earlier => "easing"; else
    "steady". If net_burn_rate <= 0 => trend "filling".
  * minutes_to_depletion = (current_balance - safety_floor) / projection_rate. If filling/not
    depleting => null (and projected_depletion_ts => null). safety_floor is per-pool config (not 0).
  * projected_depletion_ts = generated_at + minutes_to_depletion.
  * CONFIDENCE (0..1, earned — expose confidence_factors): higher when burn-rate variance is low,
    higher with larger sample_size (txn count in window), and multiplied by meta.confidence_modifier
    (data freshness). Document the formula in code comments.
  * STATUS from minutes_to_depletion thresholds (config defaults: <30 critical, <90 watch, else
    healthy; filling => healthy). This is the SINGLE SOURCE OF TRUTH for pool status.
  * recommended_action: advisory, provider-respecting, safe language (physical cash => "arrange cash
    support"; provider => "top up via approved channel"). NEVER "transfer from another provider".
  * evidence: 2-4 plain strings (rate, recent balance drop, trend note).
  * history: a short recent balance series (bucketed points) for the frontend burn-down chart.
- Thresholds, window sizes, safety_floors, EMA span all live in forecast config constants.

WIRING:
- GET /api/forecast -> { forecasts:[Forecast x4], meta }.
- REFACTOR /api/pools so each pool's status comes from the forecast engine (import the same status
  function) — pools and forecast must never disagree.
- Update the hero's constraining-pool concept is a frontend concern, but ensure forecast output makes
  "soonest minutes_to_depletion" trivially derivable.

TESTS (tests/):
- Known-case math: seed a deterministic pool where balance falls at a fixed net rate; assert
  minutes_to_depletion and status match the hand-computed value (within tolerance).
- Direction sanity: physical cash under cash_out pressure has positive burn (draining); the credited
  provider pool trends filling in the same window.
- Filling pool => minutes_to_depletion is null (never negative), trend "filling".
- Trend: an accelerating synthetic series is labeled "accelerating" and yields a shorter countdown
  than the flat-EMA estimate.
- Confidence: a volatile series yields lower confidence than a steady one; a stale meta
  (confidence_modifier<1) lowers it further.
- Consistency: the status in /api/pools equals the status in /api/forecast for every pool.
- VALIDATION METRIC (for the deliverable): a test/script that, on a held-out portion of the seeded
  history, measures SHORTAGE DETECTION LEAD TIME = (actual depletion time) - (time status first went
  critical). Print the number of minutes. This is one of our 3 required metrics.

TEST GATE: pytest all green; GET /api/forecast returns 4 contract-shaped forecasts; /api/pools status
matches. Paste pytest output + a sample /api/forecast response + the measured lead-time number, then
STOP. Do not start Phase 3.

##frontend

Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 2 forecast final), and ./shared/design.md.
Work ONLY inside ./frontend. Phase 1 is complete and committed.

PHASE 2 GOAL: fill the provider detail screen with the real forecast — countdown, confidence beside
the prediction, trend, evidence, recommended action, and a Recharts burn-down chart. Build on mock,
then swap to live.

API + MOCK:
- Extend lib/api.ts with getForecast() and the Forecast type from contract.md. Extend the mock
  adapter to return 4 contract-shaped forecasts including: physical_cash critical & accelerating with
  a countdown, one provider "filling" (minutes_to_depletion null), one steady, one watch. Keep the
  api<->mock flag.

PROVIDER DETAIL (/provider/[id]) — replace the Phase-1 "Forecast & warnings" placeholder:
- COUNTDOWN to depletion: human-readable minutes_to_depletion ("~100 min") AND the projected clock
  time from projected_depletion_ts. If filling/null => show "Balance stable or growing — no shortage
  projected" (no fake countdown).
- CONFIDENCE shown RIGHT BESIDE the prediction (not global). Show the % and expose confidence_factors
  (volatility / sample_size / data_freshness) on hover or in a small expandable.
- TREND indicator with icon + color: accelerating (danger), steady (neutral), easing (success-ish),
  filling (success). Magenta stays the brand accent; use status colors only for state.
- RECOMMENDED ACTION text (advisory, safe language) and the EVIDENCE list.
- RECHARTS BURN-DOWN chart: plot `history` as a solid line, then a DASHED projection line from the
  last history point to (projected_depletion_ts, safety_floor). Mark the safety_floor as a reference
  line. tabular-nums on axes/tooltip. Skip the projection line when filling.
- DataQualityBanner + confidence must react to meta (still "ok" today; wired for Phase 5).

DASHBOARD UPDATES:
- Pool card statuses now come from live /api/pools (forecast-driven) — verify they reflect forecast.
- HERO constraining pool = the pool with the SOONEST minutes_to_depletion (not just lowest balance).
  Update the hero's status chip + constraining-pool line to use forecast data.

SWAP + TEST GATE:
1. Build on mock; verify detail screen + chart render for all four trend cases (incl. filling).
2. With backend Phase 2 running, flip to live: clicking a provider shows its REAL forecast — countdown,
   confidence beside it, trend, evidence, action, and the burn-down chart drawn from real history +
   projection.
3. The hero flags the correct soonest-to-deplete pool; pool card statuses match the forecast.
Confirm all three, paste any errors, then STOP. Do not start Phase 3.