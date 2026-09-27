"""SQLite database engine + session factory. Auto-creates the DB on first run."""
from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import BASE_DIR

# Tests set NOVATECH_DB_PATH to a throwaway file *before* this module (or
# anything that imports from it) is first imported, so every module that
# does `from app.core.database import SessionLocal` ends up bound to the
# same test engine - reassigning these names after other modules have
# already imported them would NOT propagate, since `from x import y` binds
# a reference at import time.
DB_PATH = os.environ.get("NOVATECH_DB_PATH", os.path.join(BASE_DIR, "data", "novatech.db"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call every startup (no-op if they exist)."""
    # import models so they're registered on Base.metadata before create_all
    from app.models import camera, worker, zone, process, alert, event, rule  # noqa: F401
    Base.metadata.create_all(bind=engine)
