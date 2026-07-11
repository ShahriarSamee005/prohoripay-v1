# backend

Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 4 cases now final), and ./shared/our_idea.md
(#5 ownership/escalation/resolution, #9 traceability/audit trail). Work ONLY inside ./backend. Phase 3
is complete and committed.

PHASE 4 GOAL: a case-coordination module — auto-create + route a case per alert, support human
transitions (ack / escalate / resolve) with a guarded state machine and an immutable audit trail.
Advisory only: no financial actions, ever.

CASE MODULE (app/modules/cases/):
- Case + CaseEvent (audit) SQLModel tables per the contract shape.
- AUTO-CREATION: when detection raises an alert (extend Phase-3 run_detection), create a Case,
  set status raised->routed, and route by type: liquidity->field_officer, anomaly->risk_reviewer.
  Populate next_step + recommended_action (advisory, provider-respecting, safe language), sla_minutes
  (config per type), escalation_level 0. Set the alert's case_id.
- STATE MACHINE (guarded): allowed transitions
    routed -> acknowledged (ack)
    routed|acknowledged -> escalated (escalate; escalation_level+1; owner_role moves up the ladder
        field_officer/risk_reviewer -> supervisor -> area_manager)
    acknowledged|escalated -> resolved (resolve)
  Any illegal transition (e.g. resolve before ack, transition on a resolved case) => HTTP 409 with a
  safe message. Every successful transition APPENDS an actor-attributed CaseEvent and updates
  updated_ts. History is append-only (never mutated/deleted).
- ESCALATION LADDER + SLA are config. Provide an evaluate_escalations() function that, given "now",
  flags/auto-escalates cases past their SLA (append a system CaseEvent "auto-escalated: SLA exceeded").
  Wire it as a callable now; Phase 5 drives it from the sim clock. Do NOT run a background loop yet.
- PROVIDER SEPARATION: a case exposes only its own provider's data; never embed another provider's
  balances/alerts in a case payload.

ENDPOINTS (match contract): GET /api/cases (+ status/provider filters), GET /api/cases/{id},
POST /api/cases/{id}/ack|escalate|resolve (bodies per contract). GET /api/alerts now returns populated
case_id.

TESTS (tests/):
- Auto-routing: a liquidity alert -> case owner field_officer; an anomaly alert -> risk_reviewer.
- Happy path: raised->routed->ack->resolve appends 4 correctly-ordered, actor-attributed history
  entries and ends status resolved.
- Guards: resolve-before-ack => 409; any transition on a resolved case => 409.
- Escalation: escalate bumps escalation_level and moves owner_role up the ladder; a second escalate
  moves it again.
- SLA: evaluate_escalations() at a time past sla_minutes auto-escalates an un-acked case and appends
  a system event; within SLA it does not.
- Audit immutability: existing history entries are unchanged after later transitions.
- Alert linkage: after auto-creation the alert's case_id is set and matches the case.
- No financial-action surface: assert there is no endpoint/field that transfers/blocks/freezes.

TEST GATE: pytest green; a full raised->resolved lifecycle works over the API with a correct audit
trail; guards return 409. Paste pytest output + a sample GET /api/cases/{id} showing the history array,
then STOP. Do not start Phase 5.



# fronntend

Read ./CLAUDE.md, the UPDATED ./shared/contract.md (Phase 4 cases final), ./shared/design.md, and
./shared/our_idea.md (#5 ownership/escalation/resolution). Work ONLY inside ./frontend. Phase 3 is
complete and committed.

PHASE 4 GOAL: the connected-narrative payoff — turn the Phase-3 alert drawer's "Coordination"
placeholder into a live case panel showing owner, recommended next step, status, and working
Acknowledge / Escalate / Resolve actions with a visible audit timeline. This is the tiebreaker demo
(Scenario D end-to-end).

API + MOCK:
- Extend lib/api.ts with getCases(), getCase(id), ackCase(id,body), escalateCase(id,body),
  resolveCase(id,body) and the Case + CaseEvent types. Extend the mock with cases in different states
  (routed, acknowledged, escalated, resolved) and full history arrays.

CASE PANEL (inside the alert detail drawer, replacing the Phase-3 Coordination placeholder):
- Header: WHO OWNS IT (owner_role), current STATUS (status pill with clear colors), escalation_level,
  provider, and sla_minutes / a simple "SLA" indicator.
- RECOMMENDED NEXT STEP + recommended_action (advisory language, prominent).
- ACTION BUTTONS: Acknowledge, Escalate, Resolve — each calls the API, optimistically updates, and
  disables actions that are illegal for the current status (mirror the backend guards so users can't
  attempt a 409). Resolve opens a small note field ("reason for resolution"). NO block/freeze/transfer
  buttons exist anywhere.
- AUDIT TIMELINE: render history[] as a vertical timeline (stage, actor, time, detail), newest at
  bottom, visually emphasizing the raised->...->resolved progression. This is the "traceable
  coordination path" judges look for.
- CONNECTED STORY: from an alert's evidence, the user can see it flow into owner -> ack -> escalate ->
  resolve without leaving the drawer. Ensure the thread reads as ONE story: alert -> evidence ->
  owner -> resolution.

CASES OVERVIEW (lightweight, reinforces coordination — still part of the connected dashboard):
- A compact "Active cases" strip/section on the dashboard listing open cases with status + owner,
  clicking one opens the same drawer. Resolved cases visibly drop out of "active".

SWAP + TEST GATE:
1. Build on mock; verify the panel, action buttons (with correct enable/disable per status), and the
   audit timeline render across states.
2. With backend Phase 4 running, flip to live: pick a real alert -> open its case -> Acknowledge ->
   Escalate -> Resolve, each persisting and appending to the live audit timeline; status + owner
   update correctly and illegal actions are prevented.
3. The end-to-end thread (alert -> evidence -> owner -> ack -> escalate -> resolve) is demoable in the
   UI without a page reload; resolved cases leave the active list.
Confirm all three, paste any errors, then STOP. Do not start Phase 5.