Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 6 /api/explain final), ./shared/design.md,
and ./shared/our_idea.md (#7 inclusive Bangla comms). Work ONLY inside ./frontend. Phase 5 is complete
and committed.

PHASE 6 GOAL: add natural-language explanations (EN / বাংলা / Banglish) to alerts and forecasts via
/api/explain, with a language toggle, graceful loading/fallback, and a subtle transparency indicator
of whether the text is AI-generated or a template. Explanations are ADDITIVE — they never replace the
authoritative numbers/evidence already shown.

API + MOCK:
- lib/api.ts: explain({kind, id, lang}) -> { text, lang, source, kind, id }. Mock returns canned
  en/bn/banglish text for a forecast and an alert, plus a source:"fallback" example.

UI:
- ALERT DRAWER (Phase 3/4): add an "Explanation" block that calls explain(kind:"alert", id, lang).
  Show the text, a language toggle (EN | বাংলা | Banglish) that re-fetches, a small loading shimmer
  while Groq responds, and a subtle badge indicating source ("AI" for groq vs "Auto" for fallback) so
  it's transparent — never hide that a fallback was used.
- PROVIDER FORECAST DETAIL: same Explanation block for explain(kind:"forecast", id:pool_id, lang) —
  a plain-language read of the countdown/trend/recommended action.
- The Phase-3 Bangla alert line can now be powered by /api/explain (bn) instead of the static string;
  keep it working if the request fails (show cached/fallback text, never a blank).
- Language toggle preference persists for the session.
- CRITICAL: the explanation sits ALONGSIDE the evidence list, numbers, and confidence — it does not
  replace them. Authoritative data stays visible and unchanged.
- Safe language only (backend guarantees it; don't post-process the text).

TEST GATE:
1. Mock: explanation block renders on an alert and a forecast; language toggle switches EN/বাংলা/
   Banglish; the source badge shows for a fallback example.
2. Live (backend Phase 6 running, GROQ_API_KEY set): real Groq explanations appear on a real alert and
   a real forecast; toggling language re-fetches; loading state shows briefly.
3. Fallback path: with the key unset/backend forced to fallback, the block still shows readable text
   with the "Auto" badge — no blank, no error surfaced to the user.
Confirm all three, paste any errors, then STOP. Do not start Phase 7.

Read ./CLAUDE.md and ./shared/dos.md. Work ONLY inside ./backend, ONLY in the synthetic-data generator
and the alerts/detection module. DO NOT touch the forecast module — its projection math is final.
TIMEBOX: keep this small and safe; all existing tests must still pass.

GOAL: add temporal seasonality to the synthetic data, and make anomaly baselines TIME-AWARE (relative
to expected volume for that hour/day) instead of static.

1) SEASONALITY PROFILE (generator, config-driven constants):
   - HOUR_OF_DAY multipliers: a realistic intraday curve (quiet overnight, morning ramp, midday/
     afternoon peak, evening taper).
   - DAY_OF_MONTH multipliers: a salary-cycle uplift for roughly the 1st-7th.
   - FESTIVAL multiplier: an Eid window uplift (already have eid_rush flags — drive them from this).
   - Transaction volume at any sim moment = base_rate * hour_mult * day_mult * festival_mult.
   - TXN MIX also shifts: salary period => cash-in heavy (drains PROVIDER float, grows physical cash);
     Eid => cash-out heavy (drains PHYSICAL CASH, grows provider float). Keep direction-aware
     pool_effects exactly as-is.
   - Keep the fixed seed. Existing scenario (Eid, physical-cash-constrained) must still reproduce.

2) SALARY-DAY SCENARIO (new, for the demo): a seeded/triggerable scenario where heavy cash-in depletes
   a PROVIDER's float BEFORE physical cash — the inverse stress pattern. Verify the existing forecast
   (unchanged) correctly surfaces that provider as the constraining pool.

3) TIME-AWARE ANOMALY BASELINES (alerts module):
   - Replace static/hardcoded thresholds with EXPECTED VOLUME FOR THIS HOUR/DAY from the seasonality
     profile. Flag on deviation from the seasonal baseline (e.g. observed vs expected ratio), not from
     a global average.
   - The off-hours-burst rule becomes relative: "8x the normal volume for this hour", not "night =
     unusual".
   - Evidence strings must state the baseline explicitly, e.g. "expected ~3 txn/min at this hour;
     observed 15/min".

TESTS:
- Existing tests all still pass (esp. balance integrity, direction rule, forecast, precision/recall).
- Normal high-volume at a NORMALLY-BUSY hour is NOT flagged (baseline absorbs it).
- Same volume at a NORMALLY-QUIET hour IS flagged, with an evidence string citing the hour's baseline.
- Salary-day scenario: a provider's float depletes before physical cash; forecast marks that provider
  as the constraining pool.
- False-positive rate is re-measured and printed (should not worsen).

TEST GATE: pytest green; print the re-measured FP rate. Paste output, then STOP.
IF THIS IS NOT GREEN QUICKLY, SAY SO — we will revert rather than risk the build.