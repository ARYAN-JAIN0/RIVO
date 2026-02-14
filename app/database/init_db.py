import logging

from app.core.startup import bootstrap
from app.database.db import engine
from app.database.models import Base


def init_db() -> None:
    bootstrap()
    Base.metadata.create_all(bind=engine)
    logging.getLogger(__name__).info("database.tables.created", extra={"event": "database.tables.created"})


if __name__ == "__main__":
    init_db()
