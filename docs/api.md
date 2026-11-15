# AYE API Contract (Initial)

Base path: `/api/v1`. JSON requests and responses use snake_case. Errors use standard HTTP status codes and a stable `{ "detail": "..." }` shape. UUIDs identify resources. `/health` is public. All data routes require `Authorization: Bearer <AYE_API_TOKEN>`, configured with a random value of at least 32 characters. This is single-owner local access control, not multi-user identity or a production tenancy model.

## Foundation endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | Process health; no dependency secrets or internals |
| GET | `/auth/verify` | Validate local bearer token |
| GET | `/channels` | List configured channels |
| POST | `/channels` | Create a channel configuration |
| GET | `/channels/{channel_id}` | Retrieve configuration |
| PATCH | `/channels/{channel_id}` | Update supplied configuration fields |
| DELETE | `/channels/{channel_id}` | Remove a configuration with no dependent content; returns 409 when ideas reference it |

Channel fields: `name` (required), `niche`, `language`, `target_country`, `description`, `is_active`. IDs, timestamps, YouTube identity, OAuth status, and workflow state are server-owned. The API does not claim that a configured channel is connected to YouTube.

## Remaining resource groups

Source packs preserve RSS metadata and URLs but do not verify factual claims. Manual evidence dossiers store a human-entered summary, claims, HTTPS citations, and explicit assessment notes; AYE does not fetch citations or independently verify any statement. AI research synthesis, live YouTube publishing/analytics, and agent-run monitoring are not implemented. Human approval is available only for exact production versions with technical QA; publishing routes must additionally enforce channel ownership and OAuth authorization.

## Opportunity and content endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/ideas?channel_id=&limit=50` | List ranked opportunities |
| POST | `/ideas` | Create an idea with explicit human estimates; trend velocity comes from linked RSS item |
| GET | `/ideas/{id}/scripts` | List immutable script versions |
| POST | `/ideas/{id}/scripts` | Save a human-authored script version, optionally snapshotting same-trend manual dossiers and their citations into its content hash |
| GET | `/ideas/{id}/storyboards` | List storyboard versions |
| POST | `/ideas/{id}/storyboards` | Save scenes linked to an exact script version and content hash |
| POST | `/ideas/{id}/render-preview?storyboard_version_id=` | Render a silent graphic animatic preview with FFmpeg |
| POST | `/ideas/{id}/render-production?storyboard_version_id=` | Render scenes from rights-confirmed user image/audio assets and run technical QA |
| POST | `/ideas/{id}/render-production-queue?storyboard_version_id=` | Queue a production render for the local PostgreSQL worker; returns a durable attempt ID |
| GET | `/media-assets` | List uploaded image/audio assets and provenance |
| POST | `/media-assets` | Upload supported media with rights attestation and license/source fields |
| GET | `/media-assets/{id}/file` | Retrieve an uploaded asset |
| POST | `/videos/{id}/approvals` | Record a human decision bound to the current content hash |
| GET | `/videos/{id}/approvals` | List immutable approval decisions |
| GET | `/videos?idea_id=&limit=50` | List rendered previews |
| GET | `/videos/{id}` | Retrieve preview metadata |
| GET | `/videos/{id}/file` | Download the MP4 preview |
| GET | `/videos/{id}/captions` | Download the generated scene-timed WebVTT caption sidecar |
| GET | `/workflows/ideas/{idea_id}/events?limit=100` | Read the recorded content workflow timeline (1–500 recent events) |
| GET | `/analytics/csv-template` | Download the normalized analytics CSV header |
| POST | `/analytics/import?channel_id=` | Import cumulative CSV snapshots for a configured channel |
| GET | `/analytics/channels/{channel_id}` | Summarize the latest imported row for each video |
| GET | `/analytics/channels/{channel_id}/insights` | Return exploratory metric comparisons for channel learning |
| GET | `/analytics/channels/{channel_id}/experiments` | List manual channel experiments with latest imported group medians |
| POST | `/analytics/experiments` | Register a hypothesis, one variable, disjoint video groups, and outcome metric |
| PATCH | `/analytics/experiments/{experiment_id}` | Add notes or advance an experiment through planned, running, completed, or cancelled |
| GET | `/operations/render-usage?days=30` | Summarize local production render duration, bytes, and outcomes for 1–365 days |
| GET | `/operations/media-integrity` | Check local referenced media files and report mismatches, missing files, unsafe references, and up to 100 orphans |
| GET | `/operations/production-attempts?limit=50` | List durable render attempt states and whether running attempts have become stale |
| GET | `/operations/workers` | List background worker heartbeats, liveness, and last reported active attempt |
| GET | `/operations/production-attempts/{attempt_id}` | Poll the durable queued/running/completed/failed attempt status |
| POST | `/operations/production-attempts/{attempt_id}/recover` | Close a stale interrupted attempt, count it against the retry ceiling, and clean its partial outputs |
| GET | `/publishing/jobs` | List local publishing schedule records; these are not YouTube uploads |
| POST | `/publishing/jobs` | Save a future private-only schedule after explicit human review of exact title, description, tags, and visibility |
| DELETE | `/publishing/jobs/{job_id}` | Cancel a local schedule record |
| GET | `/dashboard/summary` | Return persisted channel, trend, idea, and render summary counts with recent items |

The opportunity score uses the blueprint's weighted formula. The RSS heuristic is used as the trend-velocity input, and engagement, audience relevance, originality, and research quality are user estimates. Script and storyboard endpoints save human input; they do not claim AI generation.

Script requests may include up to 20 `research_document_ids` and at most 500 KB of combined dossier snapshots; every ID must be a manual dossier for the trend linked to that idea. The script version stores an immutable snapshot of each dossier and its citations, and the script hash covers both body and snapshots. That hash flows into production approval fingerprints through the exact script version. This preserves provenance without asserting that citations or claims are correct.

Preview rendering creates scene cards from storyboard text and exports a silent MP4. Production renders use the blueprint's target sizes: 1080×1920 for Shorts and 1920×1080 for long-form. They require a rights-attested image and audio asset for every scene, use scene-level subtitle overlays, generate a thumbnail and scene-timed WebVTT sidecar, and check MP4/H.264/AAC, resolution, duration, captions, and source-file integrity. WebVTT cue timing follows storyboard scene durations; it is not speech-recognition or word-level synchronization. Human approval requires four review confirmations, checks that source/render/caption files and version hashes still match, and rejects stale script/storyboard versions. Technical QA does not verify editorial claims or the truth of user-supplied license declarations. Approval is not YouTube publish authorization. Files are stored in the `aye_media` Docker volume.

Analytics CSV imports require the exact header from `/analytics/csv-template`. CTR is a percentage from 0 to 100; dates must be ISO formatted; each row is a cumulative snapshot for one video/date. Summaries select the latest imported row per video and label small samples. Learning insights compare median CTR and average view duration between the highest-view and lowest-view quartile groups when at least 10 videos are available. Evidence strength is based on sample count only; comparisons are exploratory, do not adjust for video age, format, topic, or promotion, do not imply causation, and never change strategy automatically. No live provider API is connected.

Manual content experiments require disjoint control and treatment lists of YouTube video IDs. Their outcome medians use the latest imported snapshot available for each listed video. Missing snapshots remain visible through group sample counts. Group assignment is user-provided; comparisons are descriptive, are not significance tests, and do not establish causal effects. Status transitions are `planned → running → completed` or `cancelled`; completed and cancelled experiments are terminal.

Workflow events are appended in the same transaction as idea creation, script/storyboard saves, render successes/failures, and human approval decisions. A queued production attempt is committed before the worker claims it; the worker marks it `running` before media rendering starts and finalizes it with the result. A worker interruption leaves a visible durable attempt. Operations marks queued or running attempts stale after `AYE_PRODUCTION_STALE_AFTER_SECONDS` (default six hours, allowed 60–172800 seconds). An operator can explicitly recover a stale attempt, which removes its attempt-specific partial outputs where possible, records a failure event, and counts it against `AYE_MAX_PRODUCTION_ATTEMPTS` (default 3, allowed 1–10). Review the source assets and render environment before retrying. This is operator-driven interruption recovery, not automatic retry scheduling or resumable FFmpeg checkpoints.

Production render requests for the same idea/storyboard are serialized by a PostgreSQL transaction-scoped advisory lock. A replay reuses an intact, passing render for the same storyboard and media inputs when it has no final decision, returning HTTP 200. If that exact render already has an approval decision, another request returns 409 so a new video row cannot silently create a second decision for the same render. A partial unique index permits only one queued or running attempt per idea/storyboard. Missing or changed files are never reused. The Compose worker claims queued attempts with `FOR UPDATE SKIP LOCKED`; stale queued or running attempts need manual recovery, and FFmpeg progress is not checkpointed.

The operations usage endpoint reports measured production render wall time, source-media bytes, output bytes, and technical outcomes from workflow events. Historical events without measurement fields are counted as unmeasured. It does not estimate electricity, rupee cost, cloud usage, LLM usage, or YouTube API charges.

The read-only media integrity endpoint hashes source assets and rendered videos where checksums are recorded, verifies that referenced files remain inside the configured media directory, and checks thumbnails for presence. It does not delete or repair files.

Production rendering can run synchronously through `/render-production` or be submitted through `/render-production-queue`. The queue stores an attempt before returning; the Compose worker claims queued rows with PostgreSQL `FOR UPDATE SKIP LOCKED`, then runs the same preflight and render service. Repeated work for the same idea/storyboard is rejected while queued or running. Queue attempts still require rights-confirmed media and technical QA; human approval remains a separate action. The worker refreshes a durable heartbeat during idle polling and long renders; `/operations/workers` reports heartbeat age and the last reported attempt. A worker crash leaves a running row for operator recovery after the configured stale timeout; a stopped worker leaves queued rows recoverable after that same timeout.

Local publishing schedules require a passing production QA result, an `approve` human decision for the currently active content hash, intact source/render files, and a future timezone-aware schedule. The schedule request must explicitly attest that the exact title, description, tags, and private visibility were reviewed; the API stores a canonical metadata hash and review timestamp alongside the content approval hash. Any changed metadata requires a new explicit review. Visibility is fixed to `private`. These records prepare metadata and timing only; no OAuth, upload, or external scheduling call exists yet. Any future publisher must validate both approval hashes and the metadata review timestamp before upload.

## Trend intelligence

| Method | Path | Behavior |
|---|---|---|
| GET | `/trends?limit=50` | List stored trend candidates ordered by heuristic score |
| POST | `/trends/discover` | Fetch configured HTTPS RSS feeds, deduplicate, and upsert items |
| POST | `/research/trends/{id}/source-packs` | Snapshot synopsis provenance and article links as an unverified source pack |
| POST | `/research/trends/{id}/dossiers` | Save a versioned manual evidence dossier with per-claim HTTPS citations and human assessment notes |
| GET | `/research/trends/{id}` | List saved source-pack and manual dossier versions |

Feeds are configured with comma-separated `AYE_RSS_FEED_URLS`. Discovery rejects non-HTTPS and non-public hosts, disables redirects, limits response size, and reports per-feed failures. The score is source diversity (up to 60) plus recency (up to 40); it is not an audience or view prediction.

Manual dossiers accept 1–50 claims, each with 1–8 HTTPS citations. Non-unreviewed assessments require a human note and are labeled `human_entered`; the saved note states that citation URLs, excerpts, and claims have not been independently checked. Citation links are not fetched. These records improve traceability but are not fact-check results or proof of claim accuracy.
