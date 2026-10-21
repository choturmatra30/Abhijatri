# Abhijatri
Abhijatri is a Bangla-first, offline-ready travel companion for Bangladesh. It helps travelers discover destinations through source-dated guides, real community experiences, transparent ratings, safety alerts, and contextual trip-cost estimates—while downloadable travel packs keep essential information available even without internet.

## Current implementation

The first development slice is the review lifecycle: Guest submission, permanent offline-draft deduplication, moderation, publication, stable feed pagination, Guest Feedback aggregation, receipt-based management, and withdrawal.

- [`Features/Review.md`](Features/Review.md): frozen review-system specification and acceptance rules.
- [`Docs/Decisions.md`](Docs/Decisions.md): implementation decisions made after specification freeze.
- [`backend/`](backend/): FastAPI modular monolith, PostgreSQL models, Alembic migration, and tests.
- [`frontend/`](frontend/): Vite + React 18 + TypeScript PWA with Tailwind CSS and modular API layer (`client.ts`, `health.ts`, `destinations.ts`, `reviews.ts`). Destination and Guest review screens use the live API; see [`Docs/Frontend-Implemented.md`](Docs/Frontend-Implemented.md).
- [`compose.yaml`](compose.yaml): local PostgreSQL service.

See [`backend/README.md`](backend/README.md) for local backend setup and [`frontend/`](frontend/) for client dev server commands.
- [`Docs/Design.md`](Docs/Design.md): UI/UX design tokens, ColorHunt botanical sage & neon slate palettes, and typography specifications.


## Architecture and delivery

```text
React PWA -> HTTPS -> FastAPI (Render) -> SQLAlchemy/Psycopg -> Supabase-managed PostgreSQL
```

- [`Docs/Architecture.md`](Docs/Architecture.md): system flow, modules, environments, environment variables.
- [`Docs/UI-Architecture.md`](Docs/UI-Architecture.md): bilingual information architecture, flows and component map (F03).
- [`Docs/Schema.md`](Docs/Schema.md): ERD and table catalogue.
- [`Docs/api/API.md`](Docs/api/API.md): versioned API contract and snapshot.
- [`Docs/Implemented.md`](Docs/Implemented.md): evidenced implementation status ([`Backend-Implemented.md`](Docs/Backend-Implemented.md), [`Frontend-Implemented.md`](Docs/Frontend-Implemented.md) hold the detail).
- [`render.yaml`](render.yaml) and [`.github/workflows/ci.yml`](.github/workflows/ci.yml): deployment blueprint and CI.
