# Abhijatri backend

This directory starts with the first required vertical slice:

```text
Guest review submission -> moderation -> publication -> guest aggregate update
```

It deliberately excludes Redis, CDN integration, and media processing until the PostgreSQL transaction and concurrency tests pass.

## Local setup

```bash
docker compose up -d postgres
cd backend
uv sync --dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The default development database URL is:

```text
postgresql+psycopg://abhijatri:abhijatri_dev@localhost:5432/abhijatri
```

Integration tests require a separate database through `TEST_DATABASE_URL`:

```bash
TEST_DATABASE_URL=postgresql+psycopg://abhijatri:abhijatri_dev@localhost:5432/abhijatri_test \
  uv run pytest -m integration
```

Tests intentionally do not fall back to SQLite because row locks, PostgreSQL partial indexes, and concurrent rating transitions are part of the feature contract.

