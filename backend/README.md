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


## Environment variables

See `.env.example` and `Docs/Architecture.md` section 5. Copy `.env.example` to `.env`; never commit `.env`.
Generate a pepper with `python -c "import secrets;print(secrets.token_urlsafe(48))"`.
If a local PostgreSQL service already owns port 5432, run `POSTGRES_PORT=55432 docker compose up -d postgres` and use that port in the URLs.

## Checks (same as CI)

```bash
uv run ruff check .
uv run pytest -m "not integration"
uv run alembic upgrade head && uv run alembic check
TEST_DATABASE_URL=postgresql+psycopg://abhijatri:abhijatri_dev@localhost:5432/abhijatri_test uv run pytest -m integration
```

## Deploy (Render + Supabase)

1. Supabase: create the project, copy the **Session pooler** URI (port 5432) and append `?sslmode=require`. Do not use the direct host (IPv6-only) or transaction mode.
2. Render: New > Blueprint > select this repo (`render.yaml`). Enter `DATABASE_URL` and `CORS_ALLOWED_ORIGINS`; `RECEIPT_PEPPER` is generated.
3. The container runs `alembic upgrade head` then starts uvicorn. Verify `/api/v1/health` and `/api/v1/health/ready`.
4. Roll back by redeploying the previous Render deploy; downgrade migrations manually only after reviewing data impact.
