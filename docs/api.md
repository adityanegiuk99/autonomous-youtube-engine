# AYE API Contract (Initial)

Base path: `/api/v1`. JSON requests and responses use snake_case. Errors use standard HTTP status codes and a stable `{ "detail": "..." }` shape. UUIDs identify resources. Authentication is intentionally not implemented in the foundation slice; do not expose this API to an untrusted network until authentication and authorization are added.

## Foundation endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | Process health; no dependency secrets or internals |
| GET | `/channels` | List configured channels |
| POST | `/channels` | Create a channel configuration |
| GET | `/channels/{channel_id}` | Retrieve configuration |
| PATCH | `/channels/{channel_id}` | Update supplied configuration fields |
| DELETE | `/channels/{channel_id}` | Remove a configuration with no dependent content |

Channel fields: `name` (required), `niche`, `language`, `target_country`, `description`, `is_active`. IDs, timestamps, YouTube identity, OAuth status, and workflow state are server-owned. The API does not claim that a configured channel is connected to YouTube.

## Planned resource groups

Trends and ideas, source-backed research, script/storyboard versions, video and QA, approvals, publish jobs, analytics, and agent runs will be added as their domain contracts are implemented. Approval and publishing routes must bind to immutable content versions and enforce ownership.
