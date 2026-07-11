# ProhoriPay — Backend

Modular FastAPI service for the ProhoriPay advisory decision-support prototype.
See the repo root `CLAUDE.md` and `shared/contract.md` for guardrails and the API contract.

## Layout

```
app/
  main.py                    # thin app: CORS, DB init, module routers
  common/
    meta.py                  # shared `meta` envelope (degraded-data convention)
  core/
    config.py                # pydantic-settings (reads .env)
    db.py                    # SQLModel engine, init_db(), get_session
    enums.py                 # contract core enums (PoolId, Provider, TxnType, ...)
    effects.py               # THE one direction-aware pool-effects helper
    models.py                # SQLModel tables: Agent, Pool, Transaction
    seed.py                  # `python -m app.core.seed` — (re)create + populate DB
  modules/
    health/router.py         # GET /health
    agent/                   # GET /api/agent
    pools/                   # GET /api/pools
    transactions/            # GET /api/transactions
    synth/                   # synthetic-data generator (Faker + numpy, fixed seed)
tests/
  conftest.py                # seeds an isolated test DB, overrides get_session
  test_health.py  test_endpoints.py  test_integrity.py
  test_direction.py  test_anomalies.py
```

Each feature is a **self-contained module** (router + schemas + its own tests).
No business logic lives in `main.py`.

### The core domain rule (direction-aware transactions)

Physical cash (shared drawer) and provider e-money (separate per provider) drain in
**opposite** directions. Every transaction's `pool_effects` is built by the single helper
`app/core/effects.py`, so the rule can never drift:

- `cash_out` → `physical_cash −amount`, `provider +amount` (customer walks away with cash)
- `cash_in`  → `physical_cash +amount`, `provider −amount` (customer deposits cash)

The `Transaction` table also stores server-side-only ground-truth labels
(`is_injected_anomaly`, `anomaly_type`) used purely for Phase-3 validation. These are
**never** included in any API response.

## Setup

```bash
cd backend
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate

pip install -r requirements.txt
# or, editable with dev extras:  pip install -e ".[dev]"

cp .env.example .env   # then fill in values as needed
```

## Seed the database

The synthetic dataset is deterministic (fixed seed + fixed reference clock), so every run
is identical. This drops, recreates, and repopulates the SQLite DB:

```bash
python -m app.core.seed
```

It seeds one super agent (**Karim Store**, Sylhet-Zindabazar), its four balance pools, and a
~3-hour Eid-rush transaction history. Physical cash is deliberately the **constraining**
(critical) pool at ৳80,000 while the combined total stays healthy — the hidden-shortage
scenario. It also injects three clusters of labeled anomalies (structuring, velocity spike,
off-hours burst) for later precision/recall measurement.

## Run

```bash
python -m app.core.seed      # populate the DB first
uvicorn app.main:app --reload
```

- Health:          http://localhost:8000/health → `{ "status": "ok", "time": "...Z" }`
- Agent:           http://localhost:8000/api/agent
- Pools:           http://localhost:8000/api/pools
- Transactions:    http://localhost:8000/api/transactions?limit=50&provider=bkash
- Interactive docs: http://localhost:8000/docs

> If port 8000 is already in use on your machine, run with `--port <free-port>`.

## Test

```bash
pytest
```

Tests seed their own isolated database, so you don't need to run the seed first.
