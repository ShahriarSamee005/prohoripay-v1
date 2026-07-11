"""Seed entrypoint: (re)create and populate the SQLite database.

    python -m app.core.seed

Drops and recreates all tables, then fills them with the deterministic
synthetic dataset. Safe to run repeatedly — it always produces the same result.
"""

from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel

# Import models so their tables register on SQLModel.metadata before create_all.
from app.core import models  # noqa: F401
from app.modules.cases import models as _case_models  # noqa: F401
from app.core.db import engine as default_engine
from app.modules.synth.generator import populate


def seed_database(engine: Engine | None = None, *, reset: bool = True) -> dict:
    """Populate `engine` (defaults to the app engine) with synthetic data.

    Args:
        engine: target SQLAlchemy engine. Defaults to the configured app engine.
        reset: when True (default), drop and recreate all tables first.

    Returns:
        A summary dict of what was generated.
    """
    engine = engine or default_engine
    if reset:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    from app.modules.alerts.service import run_detection

    with Session(engine) as session:
        summary = populate(session)
        detection = run_detection(session)
    summary["alerts"] = detection
    return summary


def main() -> None:
    summary = seed_database()
    print("Seeded ProhoriPay database:")
    print(f"  agent:        {summary['agent_id']}")
    print(f"  transactions: {summary['transactions']}")
    print(f"  anomalies:    {summary['anomalies']} (server-side only, never in API)")
    print("  pools:")
    for pool_id, info in summary["pools"].items():
        print(
            f"    {pool_id:<14} opening={info['opening']:>9,}  "
            f"current={info['current']:>9,}  status={info['status']}"
        )
    alerts = summary.get("alerts", {})
    print(f"  alerts:       {alerts.get('total', 0)} "
          f"({alerts.get('anomaly', 0)} anomaly, {alerts.get('liquidity', 0)} liquidity)")
    if alerts.get("by_type"):
        print(f"    anomaly types: {alerts['by_type']}")


if __name__ == "__main__":
    main()
