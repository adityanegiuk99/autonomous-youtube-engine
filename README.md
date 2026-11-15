# Autonomous YouTube Engine (AYE)

AYE is planned as a human-approved, multi-channel content operations platform. The repository is at the start of **Phase 1: Foundation**. The current slice includes a FastAPI service, PostgreSQL persistence and migration, a Next.js dashboard with a channel setup/list page, and channel CRUD endpoints.

## Run locally with Docker

From the repository root:

```sh
docker compose up --build
```

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>
- Channel API: <http://localhost:8000/api/v1/channels>

The Compose database credentials are for local development only. Do not expose this configuration to a public network or reuse it in production. The API currently has no authentication or authorization and is intended only for local use.

## Run services separately

API: install `backend/pyproject.toml` dependencies in a Python 3.11+ environment, set `AYE_DATABASE_URL` (see `backend/.env.example`), run `alembic upgrade head` from `backend/`, then `uvicorn app.main:app --reload` from `backend/`.

Dashboard: use Node.js 22+, run `npm install` and `npm run dev` from `frontend/`. Set `NEXT_PUBLIC_API_BASE_URL` if the API is not at `http://localhost:8000/api/v1`.

## Current limits

Channel records are configuration only and do not indicate that a YouTube account is connected. Authentication, Google OAuth, trend discovery, agents, content generation, rendering, approval, publishing, analytics, and Redis workers are not implemented yet. See [the roadmap](docs/roadmap.md), [architecture](docs/architecture.md), [data model](docs/data-model.md), [agent contracts](docs/agent-contracts.md), and [API contract](docs/api.md).
