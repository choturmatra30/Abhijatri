import os
from collections.abc import Generator
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models  # noqa: F401
from app.db import Base


def _test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    database_name = urlparse(value.replace("postgresql+psycopg", "postgresql", 1)).path.lstrip("/")
    if not database_name.endswith("_test"):
        pytest.fail("Refusing to reset a database whose name does not end with '_test'")
    return value


@pytest.fixture()
def postgres_session() -> Generator[Session, None, None]:
    engine = create_engine(_test_database_url(), pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
        session.rollback()
    Base.metadata.drop_all(engine)
    engine.dispose()

