# Autonomous YouTube Engine (AYE)

AYE is planned as a human-approved, multi-channel content operations platform. The repository is progressing through **Phases 1–5**. It includes FastAPI, PostgreSQL migrations, channel CRUD, RSS discovery and source packs, opportunity scoring, versioned human-authored scripts/storyboards, and a silent animatic renderer.

## Run locally with Docker

From the repository root, copy `.env.example` to `.env`, generate a random token (at least 32 characters) with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, and place it in `AYE_API_TOKEN`. Add trusted HTTPS RSS URLs to `AYE_RSS_FEED_URLS` if you want to use Trend Radar. Then run:

```sh
docker compose up --build
```

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>
- Channel API: <http://localhost:8000/api/v1/channels>
- Trend Radar: <http://localhost:3000/trends>
- Content pipeline: <http://localhost:3000/ideas>

The dashboard prompts for the token and keeps it in browser session storage. The Compose database credentials are for local development only. The bearer token is single-owner local access control, not production authentication or multi-user authorization; do not expose this stack publicly.

## Run services separately

API: install `backend/pyproject.toml` dependencies in a Python 3.11+ environment, set `AYE_DATABASE_URL` and a random `AYE_API_TOKEN` of at least 32 characters (see `backend/.env.example`), run `alembic upgrade head` from `backend/`, then `uvicorn app.main:app --reload` from `backend/`.

Dashboard: use Node.js 22+, run `npm install` and `npm run dev` from `frontend/`. Set `NEXT_PUBLIC_API_BASE_URL` if the API is not at `http://localhost:8000/api/v1`.

Configure `AYE_RSS_FEED_URLS` as a comma-separated list of trusted HTTPS feeds before using Trend Radar. Discovery limits response size and rejects non-public feed hosts. The score is a transparent freshness/source-diversity heuristic; it does not estimate likely views.

Set `AYE_RSS_FEED_URLS` in root `.env` for Docker Compose, or in `backend/.env` when running the API directly. Opportunity scoring uses the blueprint's weights, but only the RSS score is automated; other factors are supplied as human estimates. Script and storyboard records are human-authored versions, not generated output.

The video preview endpoint creates a silent text-card animatic from a storyboard. It is not a publishable video and does not have voice, licensed imagery, captions, thumbnails, or QA approval.

## Current limits

Channel records are configuration only and do not indicate that a YouTube account is connected. Multi-user authentication, Google OAuth, AI research/script generation, voiced production, final QA, approval, publishing, analytics, and Redis workers are not implemented yet. See [the roadmap](docs/roadmap.md), [architecture](docs/architecture.md), [data model](docs/data-model.md), [agent contracts](docs/agent-contracts.md), and [API contract](docs/api.md).
