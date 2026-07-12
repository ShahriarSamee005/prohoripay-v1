# ProhoriPay

**Advisory decision-support dashboard for multi-provider MFS super agents**
Hackathon: bKash × SUST CSE Carnival 2026 · Synthetic data only · Advisory only · No real provider integration

---

## The Core Insight

A super agent serving bKash, Nagad, and Rocket customers shares **one physical cash drawer** but holds **three separate, non-interchangeable e-money balances**. Conventional dashboards display a combined total — which hides the critical reality:

> Provider e-money pools can appear healthy while physical cash has already run out. The healthy-looking total is misleading. A customer who asks to cash out gets turned away.

ProhoriPay separates the four pools, forecasts each one independently, and surfaces shortages **before** they happen.

---

## The Three Pillars

| Pillar | What it does |
|---|---|
| **1. Liquidity shortage prediction** | Per-pool EMA burn-rate forecast. Counts down minutes to depletion. Escalates physical cash (the constraining pool) first. Confidence falls automatically when a provider feed goes stale. |
| **2. Unusual-activity detection with evidence** | Context-aware rule detectors (structuring, velocity spike, off-hours burst). Eid-aware baselines prevent flagging legitimate festival demand. Every alert carries specific evidence — counts, amounts, account clusters, time windows — never a bare score. |
| **3. Operational coordination as a tracked case** | Every alert auto-creates a human-owned case, routed by type (liquidity → field officer; unusual activity → risk reviewer). Cases have an immutable audit trail, SLA timers, and an escalation ladder. Nothing is auto-resolved. |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router, TypeScript), Tailwind CSS, shadcn/ui, Framer Motion, Lenis, Recharts |
| Backend | FastAPI, modular (one directory per feature), SQLModel + SQLite |
| Analytics | pandas, numpy, scikit-learn — **fully deterministic, no LLM in the pipeline** |
| Synthetic data | Faker + numpy (seed 1, reference date 2026-07-11) |
| Live updates | Server-Sent Events (SSE) — `GET /api/stream` |
| Natural-language explanations | Groq (downstream translation only; falls back to deterministic templates) |

---

## Project Structure

```
prohoripay-v1/
├── backend/
│   ├── app/
│   │   ├── core/         # Config, DB engine, models, seed, effects helper
│   │   └── modules/
│   │       ├── agent/        GET /api/agent
│   │       ├── pools/        GET /api/pools
│   │       ├── transactions/ GET /api/transactions
│   │       ├── forecast/     GET /api/forecast  (EMA engine)
│   │       ├── alerts/       GET /api/alerts    (rule detectors)
│   │       ├── cases/        GET/POST /api/cases
│   │       ├── sim/          POST /api/sim/*    (clock + demo controls)
│   │       ├── llm/          POST /api/explain  (Groq + fallback)
│   │       ├── health/       GET /health
│   │       └── synth/        Generator + config (seed only, not a route)
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/              Next.js App Router pages
│   ├── components/       Dashboard, alert feed, pool breakdown, case view
│   └── lib/              API client, types, SSE stream
├── shared/
│   ├── contract.md       API shapes (source of truth)
│   ├── dos.md            Compliance checklist + MFS limits
│   └── design.md         Blossom-Vermillion design system
└── docs/
    ├── architecture.md
    ├── data-simulation.md
    ├── responsible-design.md
    └── validation.md
```

---

## Setup & Run

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Groq API key (free tier; the system runs fully without it via template fallback)

### 1. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
# Then edit .env:
```

```env
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.3-70b-versatile
DATABASE_URL=sqlite:///./prohoripay.db
CORS_ORIGINS=http://localhost:3000
```

Seed the database (deterministic; safe to rerun — always the same result):

```bash
python -m app.core.seed
```

Start the API server:

```bash
uvicorn app.main:app --reload --port 8000
```

**Interactive API docs (Swagger UI):** http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Start the dev server:

```bash
npm run dev
```

Dashboard: **http://localhost:3000**

### 3. Tests

```bash
cd backend
pytest
```

---

## How to Run the Demo

The simulation clock advances time in 5-minute ticks. Demo controls send events to the backend, which recomputes forecasts and detection in real time over SSE. Everything is presenter-driven; nothing auto-executes.

**Before starting:** open the dashboard and confirm:
- Physical cash shows the lowest headroom (the hidden-shortage scenario).
- Three anomaly alerts are already seeded (from the historical data).
- Open cases are visible in the coordination panel.

### Scenario A — Liquidity crisis

1. Click **Start** (or `POST /api/sim/start`). The clock begins at 2 ticks/sec.
2. Click **Inject Eid Rush** → `POST /api/sim/eid_rush {"provider": "physical_cash", "intensity": "high"}`.
3. Each tick applies 12 cash-out transactions (3,000–9,000 BDT each), draining physical cash.
4. Within a few ticks, physical cash crosses the **critical** threshold (< 30 minutes to the 10,000 BDT safety floor).
5. A liquidity alert fires. A case is auto-created and routed to the field officer.
6. Follow the case: Acknowledge → Escalate → Resolve.

### Scenario B — Unusual-activity cluster

1. Click **Inject Anomaly** → `POST /api/sim/inject_anomaly {"provider": "bkash", "type": "structuring"}`.
2. 8 near-identical transactions (~4,950 BDT) from 2 accounts appear on the next tick.
3. The structuring detector fires an alert (with evidence: count, mean amount, account cluster, time window).
4. A case is auto-routed to the risk reviewer.

### Scenario C — Degraded provider feed

1. Click **Break Nagad Feed** → `POST /api/sim/break_feed {"provider": "nagad", "mode": "stale"}`.
2. Nagad's `data_quality` becomes `"stale"`; its `confidence_modifier` drops to 0.4.
3. The dashboard shows a data-quality caution. Nagad's forecast confidence drops accordingly.
4. No confident alert is raised on degraded data.
5. Click **Restore Feed** → `POST /api/sim/restore_feed {"provider": "nagad"}` to return to normal.

### Scenario D — Full case lifecycle

1. From any open case: **Acknowledge** (field officer or risk reviewer).
2. If SLA is about to breach: **Escalate** (moves to supervisor).
3. After reviewing: **Resolve** with a human-written note.
4. Every step appends an immutable entry to the case audit trail.

---

## Measured Metrics

> Run the validation procedure in [`docs/validation.md`](docs/validation.md) to fill these in.

| Metric | Value | Notes |
|---|---|---|
| Shortage detection lead time | `29.6 min` | Minutes before physical cash crosses the safety floor |
| Anomaly precision | `100%` | Against 39 injected, labeled ground-truth anomalies |
| Anomaly recall | `100%` | Against 39 injected, labeled ground-truth anomalies |
| Anomaly F1 | `1.00` | Harmonic mean of precision and recall |
| False-positive rate (Eid traffic) | `0.0%` | Non-injected Eid-rush transactions covered by an anomaly alert |

---

## Further Reading

- [Architecture diagram](docs/architecture.md) — Mermaid diagram with provider-isolation lanes, analytics pipeline, Groq placement
- [Data simulation](docs/data-simulation.md) — How the synthetic data is generated; direction-aware pool effects; assumptions and limits
- [Responsible design](docs/responsible-design.md) — Privacy, human review, false-positive handling, and what this system intentionally does NOT do
- [Validation](docs/validation.md) — Metric definitions, measurement methodology, honest limitations
- [API contract](shared/contract.md) — All endpoint shapes and rules
- [Swagger UI](http://localhost:8000/docs) — Live interactive API docs (server must be running)

---

## Important Notices

- **Synthetic data only.** No real bKash, Nagad, or Rocket API is called at any point. No real account, wallet, PIN, OTP, or credential exists in this system.
- **Advisory only.** ProhoriPay notifies, explains, recommends, and tracks. It does not execute, block, freeze, transfer, top-up, or auto-approve anything. Every financial decision is made by a human.
- **No real provider integration.** This is a hackathon prototype. It has not been reviewed for production readiness, regulatory compliance, or real operational deployment.
