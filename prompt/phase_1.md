##backend

Read ./CLAUDE.md and ./shared/contract.md again. Work ONLY inside ./backend. Phase 0 is complete
and committed.

PHASE 1 GOAL: the synthetic-data foundation + the three Phase-1 endpoints, all matching contract.md
exactly. Keep main.py thin; add new modules.

MODELS (SQLModel tables, shapes exactly per contract.md — PoolId/Provider/TxnType/TxnStatus/PoolStatus
enums; Transaction.pool_effects stored as JSON list of {pool_id, delta}):
- Agent, Pool, Transaction.
- Transaction ALSO stores server-side-only ground-truth fields that are NEVER returned by any API:
  is_injected_anomaly (bool) and anomaly_type (str|null). These exist only for Phase 3 validation.

SYNTHETIC DATA GENERATOR (own module; Faker + numpy with a FIXED seed for reproducibility):
- Seed 1 primary super-agent: "Karim Store", area "Sylhet-Zindabazar", providers bkash/nagad/rocket.
  Make it config-driven so more agents can be added later, but seed just 1 now.
- Opening balances chosen so the TOTAL looks healthy but PHYSICAL CASH is the constraining pool
  (the hidden-shortage scenario): e.g. physical_cash draining toward ~80,000; bkash 150,000;
  nagad 40,000; rocket 120,000.
- Generate a realistic transaction history over the last ~3 hours, mostly "eid_rush" cash_out
  pressure on physical cash, plus normal baseline periods (event_flag: eid_rush | salary_day | null).
- DIRECTION-AWARE effects, strictly per CLAUDE.md, encoded in ONE helper so it can't drift:
  cash_out => physical_cash −amount & provider +amount ; cash_in => physical_cash +amount &
  provider −amount.
- Amounts respect the MFS per-transaction limits in shared/dos.md (realistic ranges).
- INJECT labeled anomalies of at least: (a) repeated near-identical amounts from a small account
  cluster in a short window (structuring), (b) a velocity spike, (c) an off-hours burst. Tag each
  with is_injected_anomaly + anomaly_type. Record the counts (Phase 3 measures precision/recall).
- Derive each pool's current_balance = opening_balance + sum(its signed effects); store both. Set a
  basic status (healthy/watch/critical) by simple threshold for now (Phase 2 forecast refines it).
- A seed entrypoint (e.g. `python -m app.core.seed`) that (re)creates and populates the SQLite DB.
  Document it in backend/README.md.

ENDPOINTS (match contract exactly; include meta {data_quality:"ok", confidence_modifier:1.0}):
- GET /api/agent
- GET /api/pools
- GET /api/transactions?limit=50&provider=<optional>

TESTS (tests/):
- Integrity: for every pool, stored current_balance == opening_balance + sum(signed effects).
  (This is the proof the direction rule is correct.)
- Direction: a cash_out has physical_cash delta < 0 and provider delta > 0; cash_in is the reverse.
- Anomaly: the expected number of labeled anomalies exist in the DB and appear in NO API response body.
- Endpoints: /api/agent, /api/pools (4 pools incl physical_cash), /api/transactions (items carry
  pool_effects; meta present) all return 200 with contract-shaped payloads.

TEST GATE: pytest all green; seed runs clean; the three endpoints return real seeded data. Paste the
pytest output + a sample /api/pools response, then STOP. Do not start Phase 2.

##frontend

Read ./CLAUDE.md, ./shared/contract.md, and ./shared/design.md again. Work ONLY inside ./frontend.
Phase 0 is complete and committed.

PHASE 1 GOAL: the real dashboard shell — hero (safe framing), balance breakdown, provider card row,
and a basic provider detail route — built on a mock adapter first, then swapped to the live backend.

BUILD:
- Mock adapter (lib/mock.ts) returning contract-shaped Agent, Pool[], Transaction[] including the
  hidden-shortage scenario (total healthy, physical_cash critical). Extend lib/api.ts with getAgent(),
  getPools(), getTransactions() hitting the real backend, and a single flag (env or const) that
  switches api<->mock so you can build on mock then flip to live.
- HERO CARD per contract's "Hero framing" (compliance-critical): a prominent "Total Holdings" number
  (large, tabular-nums-bv) EXPLICITLY labeled as a sum of separate, non-interchangeable pools; beside
  or under it, the CONSTRAINING pool (lowest headroom) and an operational-status chip
  (e.g. "⚠️ Physical cash critical"). Never present the total as a single spendable balance. Use the
  magenta hero recipe from design.md.
- BREAKDOWN directly beneath the hero: physical cash + each provider, each with its logo/label beside
  its amount (tabular figures). For provider logos use a clean placeholder (colored circle / initial)
  with a slot to drop real assets later.
- PROVIDER CARD ROW: one card per provider (bkash/nagad/rocket) in a row, each showing balance +
  status, each clickable → /provider/[id].
- PROVIDER DETAIL ROUTE (/provider/[id]): basic for now — provider balance, status, and that
  provider's recent transactions (getTransactions with provider filter). Leave a clearly-marked
  "Forecast & warnings" placeholder section (Phase 2 fills it).
- DataQualityBanner component reading meta.data_quality: renders nothing when "ok", a caution when
  degraded/stale. Wire it now (always "ok" today) so Scenario C is trivial in Phase 5.
- Framer Motion: subtle, tasteful card entrance transitions; respect prefers-reduced-motion.
- Semantic tokens only, magenta single accent, all money in tabular-nums-bv.

SWAP + TEST GATE:
1. Build on mock; verify the UI renders correctly.
2. With backend Phase 1 running, flip the flag to live; confirm the dashboard shows the REAL seeded
   balances (hero total, breakdown, provider cards) and the hero correctly surfaces physical cash as
   the constraining pool.
3. Clicking a provider card navigates to its detail route showing that provider's real balance +
   recent transactions.
Confirm all three, paste any errors, then STOP. Do not start Phase 2.