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
| ContentIdea | channel, trend (optional), topic, format, score components, state |
| ResearchDocument | idea, source references, claims, conflicts, generated time |
| ScriptVersion | idea, version, body/structured sections, source links, content hash |
| StoryboardVersion | script version, scenes, timing, asset requirements, content hash |
| MediaAsset | owner workflow, URI, MIME type, checksum, license/provenance, metadata |
| Video | idea, script/storyboard versions, render asset, QA status, metadata, content hash |
| Approval | video, exact content hash, reviewer, decision, notes, timestamp |
| PublishJob | video, approval, channel, visibility/schedule, idempotency key, provider ID, status |
| AnalyticsSnapshot | channel/video, period, metrics, source, collected time |
| AgentRun | workflow subject, agent/type, status, attempt, bounded logs, timestamps |
| WorkflowCheckpoint | workflow ID, subject, serialized state reference, schema version, updated time |
| AuditLog | actor, action, target, outcome, timestamp, safe metadata |

## Constraints

- Enforce channel ownership in service queries and authorization checks.
- Unique external channel identity per platform account where applicable.
- Unique `(content_idea_id, version)` for scripts/storyboards.
- Approval is valid only when the current video content hash equals the approved hash and QA is passing.
- Publish jobs are idempotent per approved video/version and destination channel.
- Never store plaintext OAuth refresh tokens; avoid secret values in logs and serialized workflow state.
- Analytics values preserve provider collection time and metric provenance; missing values are not silently converted to zero.

## Foundation implementation

Phase 1 implements only the `Channel` configuration slice with a local development database. User identity, OAuth connections, and all content lifecycle records remain future migrations. The initial API must not expose fields that imply an external account has been connected or verified.
