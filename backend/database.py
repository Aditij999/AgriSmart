"""SQLite engine, session factory and FastAPI session dependency."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from backend import models  # noqa: F401  (registers the mappers)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """create_all() never alters an existing table, so databases created before
    `grown_crop` existed get it added here (nullable, so old rows stay valid)."""
    from sqlalchemy import inspect, text

    cols = {c["name"] for c in inspect(engine).get_columns("predictions")}
    if "grown_crop" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE predictions ADD COLUMN grown_crop VARCHAR(64)"))
