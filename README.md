# Abhijatri
Abhijatri is a Bangla-first, offline-ready travel companion for Bangladesh. It helps travelers discover destinations through source-dated guides, real community experiences, transparent ratings, safety alerts, and contextual trip-cost estimates—while downloadable travel packs keep essential information available even without internet.

## Current implementation

The first development slice is the review lifecycle: Guest submission, permanent offline-draft deduplication, moderation, publication, stable feed pagination, Guest Feedback aggregation, receipt-based management, and withdrawal.

- [`Features/Review.md`](Features/Review.md): frozen review-system specification and acceptance rules.
- [`Docs/Decisions.md`](Docs/Decisions.md): implementation decisions made after specification freeze.
- [`backend/`](backend/): FastAPI modular monolith, PostgreSQL models, Alembic migration, and tests.
- [`compose.yaml`](compose.yaml): local PostgreSQL service.

See [`backend/README.md`](backend/README.md) for local setup and test commands.


## Architecture and delivery

```text
React PWA -> HTTPS -> FastAPI (Render) -> SQLAlchemy/Psycopg -> Supabase-managed PostgreSQL
```

- [`Docs/Architecture.md`](Docs/Architecture.md): system flow, modules, environments, environment variables.
- [`Docs/Schema.md`](Docs/Schema.md): ERD and table catalogue.
- [`Docs/API.md`](Docs/API.md): versioned API contract and snapshot.
- [`Docs/Implemented.md`](Docs/Implemented.md): evidenced implementation status.
- [`render.yaml`](render.yaml) and [`.github/workflows/ci.yml`](.github/workflows/ci.yml): deployment blueprint and CI.
