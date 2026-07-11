# CLAUDE.md — ProhoriPay

Both the backend and frontend Claude Code sessions read this file. It is the source of truth for
guardrails, architecture, and stack. When in doubt, this file and `shared/contract.md` win over
anything you infer.

## What this is
ProhoriPay is a decision-support prototype for multi-provider mobile-financial-service (MFS)
"super agents" (bKash, Nagad, Rocket) who serve customers from **one shared physical cash drawer**
but **separate e-money balances per provider**. It surfaces (1) liquidity pressure, (2) unusual
activity, and (3) coordination of the response. It is **advisory only**. Hackathon: bKash presents
SUST CSE Carnival 2026.

## Non-negotiable guardrails (compliance is directly scored)
- **Advisory only.** Never execute, block, freeze, transfer, top-up, or auto-approve anything.
  Humans make every financial decision. The product notifies, explains, recommends, and tracks.
- **Never the word "fraud"** (nor "suspicious", "criminal", "blocking"). Use: *unusual*,
  *requires review*, *needs attention*, *consider*, *suggest*.
- **Never a final determination.** Surface evidence + uncertainty; a human decides.
- **Provider separation is absolute.** bKash / Nagad / Rocket are logically separate systems.
  Never imply one can see, control, or convert another's balance. The ONLY shared resource is
  physical cash. No cross-wallet transfer or merge, ever.
- **Synthetic data only.** Never real APIs, wallets, accounts, PINs, OTPs, passwords, or
  credentials. Never build a login/credential form.
- **No single combined total as a health/spendable figure.** A prominent "Total Holdings" number
  is allowed ONLY when labeled as a sum of separate, non-interchangeable pools and shown next to
  the constraining pool + operational status (see `shared/contract.md` → Hero framing).

## The critical domain rule: direction-aware transactions
Physical cash (shared) and provider e-money (separate) drain in **opposite** directions. Never
treat a transaction as a generic balance reduction — every transaction is signed and pool-specific:
- `cash_out` → `physical_cash −amount`, `provider e-money +amount`  (customer walks away with cash)
- `cash_in`  → `physical_cash +amount`, `provider e-money −amount`  (customer deposits cash)

## Architecture rule: deterministic analytics vs Groq LLM
- **All prediction and detection is deterministic Python** (pandas / numpy / scikit-learn):
  reproducible, explainable, testable. This includes liquidity forecasts and anomaly detection.
- **Groq LLM only translates finished structured results into natural language** (English / Bangla /
  Banglish). It never calculates forecasts, detects anomalies, scores risk, or makes decisions.
  A deterministic template fallback must produce a readable explanation if Groq is unavailable.

## Tech stack (do not substitute)
- **Frontend:** Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui, Framer Motion, Lenis,
  Recharts. (Leaflet only if the optional hotspot map is built.)
- **Backend:** FastAPI, **modular** (each feature is a self-contained module). SQLModel/SQLAlchemy +
  SQLite. Faker + numpy for synthetic data. Server-Sent Events (SSE) for the live flow. Groq for
  natural-language explanations.
- **Analytics:** pandas, numpy, scikit-learn.

## Design system
Follow `shared/design.md` (Blossom-Vermillion). One magenta accent `#E3106D`, **no second accent**.
Use semantic tokens only — never raw hex or Tailwind's default palette (`bg-pink-500`, `bg-gray-900`).
All currency/amounts use tabular figures. Numbers are meant to be large. Status colors
(success/warning/danger) indicate state only, never decoration.

## Backend structure (modular)
Each feature ships as a self-contained module — routes + service + schemas + its own tests. A thin
`main.py` wires modules together. `core/` holds config and the DB engine/session. No business logic
in `main.py`.

## Working rules for every session
1. **Read `shared/contract.md` before writing any endpoint or API client call.** Build to the
   contract. Do not invent divergent shapes. If something is missing, note it, propose the shape in
   your output, and follow the proposal — do not silently diverge.
2. **Every module ships with tests. Do not advance a phase until its tests pass.**
3. **Do only the current phase.** Do not race ahead to future features.
4. Reference `shared/dos.md` (compliance/tiebreakers/MFS limits) and `shared/our_idea.md` (feature
   detail) when implementing.
