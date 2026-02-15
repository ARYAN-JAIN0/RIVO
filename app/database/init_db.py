import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.startup import bootstrap
import app.database.db as db_module
from app.database.models import Base

logger = logging.getLogger(__name__)
LEGACY_BASELINE_REVISION = "20260213_0001"
LEGACY_CORE_TABLES = {"leads", "deals", "contracts", "invoices"}


def _build_alembic_config(database_url: str) -> AlembicConfig:
    cfg = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _requires_legacy_baseline_stamp() -> bool:
    inspector = inspect(db_module.get_engine())
    table_names = set(inspector.get_table_names())
    if not LEGACY_CORE_TABLES.issubset(table_names):
        return False

    if "alembic_version" in table_names:
        with db_module.get_engine().connect() as conn:
            version_rows = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() or 0
        if version_rows > 0:
            return False

    if "leads" not in table_names:
        return False

    lead_cols = {col["name"] for col in inspector.get_columns("leads")}
    return "tenant_id" not in lead_cols


def _sqlite_db_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix) :]
    if raw in {":memory:", ""}:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _reset_sqlite_db(database_url: str) -> Path | None:
    db_path = _sqlite_db_path(database_url)
    if not db_path or not db_path.exists():
        db_module.reset_engine(database_url)
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.backup_{timestamp}{db_path.suffix}")
    db_module.get_engine().dispose()
    db_path.replace(backup_path)
    db_module.reset_engine(database_url)
    return backup_path


def init_db() -> None:
    bootstrap()
    active_url = db_module.get_active_database_url()
    try:
        alembic_cfg = _build_alembic_config(active_url)
        if _requires_legacy_baseline_stamp():
            command.stamp(alembic_cfg, LEGACY_BASELINE_REVISION)
            logger.info(
                "database.legacy_schema.stamped",
                extra={"event": "database.legacy_schema.stamped", "revision": LEGACY_BASELINE_REVISION},
            )

        command.upgrade(alembic_cfg, "head")
    except Exception as exc:
        if not active_url.startswith("sqlite:///"):
            raise
        backup_path = _reset_sqlite_db(active_url)
        logger.warning(
            "database.sqlite.reset_for_schema_mismatch",
            extra={
                "event": "database.sqlite.reset_for_schema_mismatch",
                "database_url": active_url,
                "backup_path": str(backup_path) if backup_path else None,
                "reason": str(exc),
            },
        )
        command.upgrade(_build_alembic_config(active_url), "head")

    Base.metadata.create_all(bind=db_module.get_engine())
    logger.info(
        "database.tables.created",
        extra={
            "event": "database.tables.created",
            "database_url": active_url,
        },
    )


if __name__ == "__main__":
    init_db()
