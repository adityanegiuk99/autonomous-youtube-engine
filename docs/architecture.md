# AYE System Architecture

## Scope and baseline

Autonomous YouTube Engine (AYE) starts as a single-owner, modular monolith. The first release prioritizes channel configuration and a dependable end-to-end content pipeline. The repository was a blank slate at adoption; this document records the intended boundaries before feature growth.

## Runtime components

- **Web:** Next.js dashboard; calls the versioned FastAPI API.
- **API:** FastAPI application, authentication/authorization boundary, validation, and orchestration entry points.
- **Worker:** background processing for discovery, research, production, publishing, and analytics. The initial scaffold does not yet run workers.
- **PostgreSQL:** durable application records and workflow state.
- **Redis:** later background queue, cache, and coordination.
- **Media storage:** local development directory initially; object storage behind an adapter later.
- **External providers:** YouTube/Google OAuth, trend and research sources, LLMs, TTS, and licensed media. Provider adapters isolate vendor-specific APIs.

Docker Compose is the local development boundary. Production deployment, secrets, backups, and observability require environment-specific decisions and are not implied by the development configuration.

## Module boundaries

`api` owns HTTP routing and request/response schemas. `channels` owns channel configuration and identity. `content` owns ideas and versioned creative artifacts. `workflow` coordinates state transitions and checkpoints. `agents` contains narrow, typed capabilities and must not own persistence or publish directly. `integrations` contains provider adapters. `production` owns media assembly and QA. `publishing` validates approvals and submits uploads. `analytics` stores snapshots and derives insights. `security` owns authentication, authorization, encryption, and audit primitives.

Modules communicate through typed service contracts and database transactions. External calls happen through adapters and should be retryable/idempotent where possible. Avoid cross-module imports of persistence internals.

## First vertical slice

Phase 1 establishes service startup, configuration, persistence wiring, a health endpoint, and channel CRUD. Later slices add user identity and OAuth, then trend intake, research, content generation, production, approvals, publishing, and analytics. The initial channel record is configuration only; it does not represent a connected or verified YouTube account.

## Trust and publishing boundary

External content, source documents, and model output are untrusted data. They cannot change system instructions or authorize actions. Publishing requires a durable approval bound to an immutable content version, successful QA, and channel ownership/authorization checks. Upload defaults to private. The publishing worker cannot create approvals. Material edits invalidate approval.

OAuth credentials must be encrypted at rest and excluded from logs and API responses. Secrets are provided through environment configuration or a production secret manager, never committed. Apply least-privilege scopes, role and channel ownership checks, request limits, audit events, and backups before production use.

The foundation uses a single shared bearer token configured by the local operator. It is checked with constant-time comparison, required on all data routers, and held in browser session storage. This protects a local single-owner instance from anonymous access but does not provide multi-user roles, account identity, or production tenancy.

## Key data relationships

- A user owns zero or more channels; a channel has one strategy and many content ideas.
- A content idea may have research dossiers, script versions, and storyboard versions.
- A rendered video references an exact storyboard/script version and its media assets.
- Approval references a video and immutable content hash; publishing jobs reference that approval.
- Local publishing schedules reference the approving decision and exact content hash. They record metadata and a private visibility intent only; no provider upload occurs.
- Analytics snapshots reference a channel and optionally a published video.
- Workflow events append the state, action, actor label, reason, and safe metadata for idea creation, content version saves, renders, and human approval decisions.
- Agent runs and workflow checkpoints reference the workflow subject and record state, attempts, and timestamps.

See [data-model.md](data-model.md) for the initial entity contract.

## Operational decisions

- API prefix: `/api/v1`.
- IDs: UUIDs; all persisted timestamps are UTC.
- State changes are explicit and validated; clients do not set internal workflow states directly.
- Provider calls have timeouts, bounded retries, and idempotency keys where the provider supports them.
- Redis/Celery and LangGraph are introduced when an actual asynchronous workflow exists, not as empty dependencies in the foundation.
- Database migrations are required before schema changes are deployed.
- Current workflow history is an audit timeline only; it does not imply background execution, retry safety, or resumable checkpoints.

## Open decisions

1. Single-user local deployment versus multi-user SaaS authentication and tenancy.
2. OAuth token encryption key management and rotation.
3. Local media retention and eventual object-storage provider.
4. Which trend and research providers fit the ₹0–₹2,000 target and their current terms/quotas.
5. Deployment target, backups, and operational monitoring.
