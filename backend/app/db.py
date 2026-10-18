from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
)


@event.listens_for(engine, "connect")
def _pin_session_to_utc(dbapi_connection, _record) -> None:
    # Poolers can hand back sessions with another timezone; always work in UTC.
    previous = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    try:
        dbapi_connection.execute("SET TIME ZONE 'UTC'")
    finally:
        dbapi_connection.autocommit = previous


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
