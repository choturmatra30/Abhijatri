## What and why
<!-- Link the Gantt task ID (e.g. F06, R04) -->

## Evidence
- [ ] `ruff check` and unit tests pass
- [ ] PostgreSQL integration tests pass (if models/services changed)
- [ ] Migration added and `alembic check` clean (if schema changed)

## Security and privacy
- [ ] No secrets, tokens or personal data in code, logs or fixtures
- [ ] New endpoints are authorised server-side and non-cacheable unless declared public
- [ ] `.env.example` and `Docs/` updated for new settings or decisions
