# Autonomous YouTube Engine (AYE)

AYE is planned as a human-approved, multi-channel content operations platform. The repository is progressing through **Phases 1–8**. It includes FastAPI, PostgreSQL migrations, channel CRUD, RSS discovery/source packs, opportunity scoring, versioned human-authored scripts/storyboards, media-backed FFmpeg rendering, technical QA, exact-version human approval, a persistent Approval Center, normalized CSV analytics imports, sample-count-labeled exploratory learning hypotheses, a per-idea workflow audit timeline, and local render resource monitoring.

## Run locally with Docker

From the repository root, copy `.env.example` to `.env`, generate a random token (at least 32 characters) with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, and place it in `AYE_API_TOKEN`. Add trusted HTTPS RSS URLs to `AYE_RSS_FEED_URLS` if you want to use Trend Radar. Production rendering allows three completed attempts per storyboard by default; set `AYE_MAX_PRODUCTION_ATTEMPTS` to an integer from 1 to 10 to adjust this cap. Then run:

```sh
docker compose up --build
```

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>
- Channel API: <http://localhost:8000/api/v1/channels>
- Trend Radar: <http://localhost:3000/trends>
- Content pipeline: <http://localhost:3000/ideas>
- Approval Center: <http://localhost:3000/approvals>
- Operations and Cost Monitor: <http://localhost:3000/operations>

The dashboard prompts for the token and keeps it in browser session storage. The Compose database credentials are for local development only. The bearer token is single-owner local access control, not production authentication or multi-user authorization; do not expose this stack publicly.

The overview dashboard reads persisted channel, trend, idea, and render counts from the API. Configured channel records are not YouTube connections, and QA-passed renders without a recorded decision may be stale if newer content versions exist.

## Run services separately

API: install `backend/pyproject.toml` dependencies in a Python 3.11+ environment, set `AYE_DATABASE_URL` and a random `AYE_API_TOKEN` of at least 32 characters (see `backend/.env.example`), run `alembic upgrade head` from `backend/`, then `uvicorn app.main:app --reload` from `backend/`.

Dashboard: use Node.js 22+, run `npm install` and `npm run dev` from `frontend/`. Set `NEXT_PUBLIC_API_BASE_URL` if the API is not at `http://localhost:8000/api/v1`.

Configure `AYE_RSS_FEED_URLS` as a comma-separated list of trusted HTTPS feeds before using Trend Radar. Discovery limits response size and rejects non-public feed hosts. The score is a transparent freshness/source-diversity heuristic; it does not estimate likely views.

Set `AYE_RSS_FEED_URLS` in root `.env` for Docker Compose, or in `backend/.env` when running the API directly. Opportunity scoring uses the blueprint's weights, but only the RSS score is automated; other factors are supplied as human estimates. Script and storyboard records are human-authored versions, not generated output.

The animatic endpoint creates silent text cards. Production rendering uses rights-attested user-uploaded images and voice audio, adds scene-level subtitle overlays and a thumbnail, and performs technical container QA. The approval endpoint binds a human decision to the rendered and source hashes and requires review confirmations. It does not independently verify content claims or license terms and is not YouTube publish authorization.

The Analytics page accepts normalized cumulative CSV snapshots and summarizes the latest row per video. With at least 10 videos, it compares CTR and average view duration across the highest and lowest view quartiles to suggest editorial review hypotheses. These comparisons are exploratory, not adjusted for age/format/topic/promotion, and do not establish causality. The page is not connected to YouTube Analytics. The Operations page measures local production render time and media bytes; it has no financial cost, cloud, or provider usage data.

## Current limits

Channel records are configuration only and do not indicate that a YouTube account is connected. Multi-user authentication, Google OAuth, AI research/script generation, TTS, publishing, live YouTube Analytics integration, and Redis workers are not implemented yet. Backups and restore require operator-managed snapshots of both PostgreSQL and media files; see [the operations runbook](docs/operations.md). See [the roadmap](docs/roadmap.md), [architecture](docs/architecture.md), [data model](docs/data-model.md), [agent contracts](docs/agent-contracts.md), and [API contract](docs/api.md).
