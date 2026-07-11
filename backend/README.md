# ProhoriPay — Backend

Modular FastAPI service for the ProhoriPay advisory decision-support prototype.
See the repo root `CLAUDE.md` and `shared/contract.md` for guardrails and the API contract.

## Layout

```
app/
  main.py                # thin app: CORS, DB init, module routers
  core/
    config.py            # pydantic-settings (reads .env)
    db.py                # SQLModel engine, init_db(), get_session
  modules/
    health/router.py     # GET /health
tests/
  test_health.py
```

Each feature is a **self-contained module** (router + schemas + its own tests).
No business logic lives in `main.py`.

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

## Run

```bash
uvicorn app.main:app --reload
```

- Health check: http://localhost:8000/health → `{ "status": "ok", "time": "...Z" }`
- Interactive docs: http://localhost:8000/docs

## Test

```bash
pytest
```
