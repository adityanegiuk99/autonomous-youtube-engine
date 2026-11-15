# AYE Data Model (Initial)

This is the conceptual model, not a claim that every table is implemented. PostgreSQL is the durable store. UUID primary keys and UTC timestamps are standard. Foreign keys use restrictive deletion for records with audit or publishing significance; large media files live outside the relational database.

| Entity | Main fields and relationships |
|---|---|
| User | id, email, password/auth provider, role, timestamps |
| Channel | id, owner user, display name, external YouTube ID (nullable until verified), niche, language, country, active flag |
| ChannelStrategy | channel, audience profile, formats, visual/voice guidelines, cadence, strategy version |
| OAuthConnection | owner/channel, provider, encrypted tokens, scopes, expiry, rotation metadata |
| TrendSource | provider, configuration, enabled state |
| TrendItem | source, canonical topic key, title, references, trend measurements, observed time |
| ResearchDocument | trend item, version, source-pack or researched dossier, structured content, immutable content hash |
| ContentIdea | channel, trend (optional), topic, format, score components, state |
| ScriptVersion | idea, version, body/structured sections, source links, content hash |
| StoryboardVersion | script version, scenes, timing, asset requirements, content hash |
| MediaAsset | storage key, type, checksum, user-attested rights, source URL, original filename |
| Video | idea, storyboard version, render asset, thumbnail, caption sidecar, media manifest, technical QA report, content hash |
| ProductionAttempt | idea, storyboard, attempt number, queued/running/completed/failed state, timestamps, output/video reference, measured usage, failure class |
| WorkerHeartbeat | worker process identity, startup and last-seen timestamps, currently claimed production attempt |
| Approval | video, exact content hash, reviewer, decision, notes, timestamp |
| WorkflowEvent | content idea, previous/current state, event type, actor, reason, safe metadata, timestamp |
| PublishJob | video, approval, channel, content hash, metadata, private visibility, local schedule, status |
| AnalyticsSnapshot | configured channel, external video ID, metrics, CSV import batch, collection time |
| ContentExperiment | channel, hypothesis, tested variable, disjoint control/treatment video IDs, metric, lifecycle, notes |
| AgentRun | workflow subject, agent/type, status, attempt, bounded logs, timestamps |
| WorkflowCheckpoint | workflow ID, subject, serialized state reference, schema version, updated time |
| AuditLog | actor, action, target, outcome, timestamp, safe metadata |

## Constraints

- Enforce channel ownership in service queries and authorization checks.
- Unique external channel identity per platform account where applicable.
- Unique `(content_idea_id, version)` for scripts/storyboards.
- Approval is valid only when the current video content hash equals the approved hash and QA is passing.
- A local publish schedule is permitted only for a passing render with a current human approval matching the exact content hash; local schedules do not imply upload.
- One local publish schedule is allowed per video; retrying the same schedule request is idempotent.
- Never store plaintext OAuth refresh tokens; avoid secret values in logs and serialized workflow state.
- Analytics values preserve provider collection time and metric provenance; missing values are not silently converted to zero.

## Foundation implementation

Implemented migrations currently cover channel configuration, trend items, opportunity ideas, human-authored script/storyboard versions, silent previews, RSS source packs, uploaded media assets, technical QA metadata and caption sidecars, content-hash-bound human approvals, imported analytics snapshots, manually registered content experiments, append-only workflow event history, local private-only publishing schedules, durable production attempt accounting, and worker heartbeat snapshots. The Compose worker claims queued attempts using PostgreSQL row locks. User identity, OAuth connections, verified research claims, resumable upload state, and live analytics integrations remain future migrations. The initial API must not expose fields that imply an external account has been connected or verified.
