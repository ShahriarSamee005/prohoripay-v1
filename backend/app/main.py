"""Application entrypoint — thin wiring only.

Creates the FastAPI app, configures CORS, initializes the database, and
includes each module's router. No business logic lives here.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db

# Import models so their tables register on SQLModel.metadata before init_db().
from app.core import models  # noqa: F401
from app.modules.agent.router import router as agent_router
from app.modules.alerts.router import router as alerts_router
from app.modules.cases.router import router as cases_router
from app.modules.forecast.router import router as forecast_router
from app.modules.health.router import router as health_router
from app.modules.llm.router import router as llm_router
from app.modules.pools.router import router as pools_router
from app.modules.sim.router import router as sim_router
from app.modules.transactions.router import router as transactions_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize the schema and lazily populate alerts if data exists."""
    init_db()
    from sqlmodel import Session

    from app.core.db import engine
    from app.modules.alerts.service import ensure_alerts

    with Session(engine) as session:
        ensure_alerts(session)
    yield


app = FastAPI(title="ProhoriPay API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module routers.
app.include_router(health_router)
app.include_router(agent_router)
app.include_router(pools_router)
app.include_router(transactions_router)
app.include_router(forecast_router)
app.include_router(alerts_router)
app.include_router(cases_router)
app.include_router(sim_router)
app.include_router(llm_router)
