from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()


def connect_args_for(configured: Settings) -> dict[str, Any]:
    """psycopg connect arguments. ``prepare_threshold=None`` turns server-side prepared statements
    off, which a transaction-mode pooler (Supabase port 6543) requires (Handoff B6)."""
    args: dict[str, Any] = {"connect_timeout": configured.db_connect_timeout}
    if not configured.uses_prepared_statements:
        args["prepare_threshold"] = None
    return args


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    connect_args=connect_args_for(settings),
)


@event.listens_for(engine, "connect")
def _configure_session(dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    # Poolers can hand back sessions with another timezone; always work in UTC.
    # Strict timeouts keep a slow query or a lock wait from holding a worker forever.
    # All values are validated integers from Settings, never request input.
    previous = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    try:
        dbapi_connection.execute(
            "SET TIME ZONE 'UTC'; "
            f"SET statement_timeout = {settings.db_statement_timeout_ms}; "
            f"SET lock_timeout = {settings.db_lock_timeout_ms}; "
            f"SET idle_in_transaction_session_timeout = {settings.db_idle_in_transaction_timeout_ms}"
        )
    finally:
        dbapi_connection.autocommit = previous


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
