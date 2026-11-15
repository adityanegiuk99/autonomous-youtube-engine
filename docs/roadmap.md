# AYE Implementation Roadmap

The attached product blueprint defines the destination. This repository starts with no application implementation, so work proceeds in vertical slices and avoids representing planned integrations as operational.

| Phase | Deliverable | Status |
|---|---|---|
| 1. Foundation | FastAPI, Next.js shell, PostgreSQL development service, configuration, channel management | Partial: local bearer token and channel CRUD UI; multi-user identity remains |
| 2. Trend intelligence | RSS/provider adapters, normalization, deduplication, scoring, Trend Radar | In progress: RSS adapter and UI |
| 3. Research and strategy | sourced dossiers, claim extraction, opportunity scoring and routing | Partial: RSS source packs, opportunity scoring, manual channel routing; claim verification pending provider |
| 4. Content generation | versioned scripts, formats, storyboard editor | Partial: versioned human script/storyboard API and Studio UI; AI generation pending provider |
| 5. Video production | voice, licensed visuals, FFmpeg, captions, thumbnails, QA | Partial: user-supplied media render, scene captions, thumbnail, technical QA; no TTS/stock integration |
| 6. Publishing | OAuth, channel verification, human approval, resumable private-first upload | Partial: exact-version human approval; OAuth/upload not started |
| 7. Analytics and learning | snapshots, comparisons, evidence-backed recommendations | Partial: normalized CSV import and descriptive sample-aware summaries; live API pending OAuth |
| 8. Integration audit | operational security, recovery, costs, integration verification | In progress: persistent Approval Center, cautious analytics learning hypotheses, workflow event history, replay guard, configurable per-storyboard attempt ceiling, measured local render resource dashboard, and operator recovery runbook; full audit pending |

## Phase 1 exit criteria

- Local services can be configured without committing secrets.
- API and dashboard have a clear, working foundation.
- Channel configuration CRUD persists records and does not imply OAuth connection.
- Database schema changes have a migration path.
- README explains setup and current limitations.

Phase 1 has a working local bearer-token gate and channel CRUD UI, but lacks multi-user identity. Phase 2 has RSS ingestion, deduplication, a source-diversity/freshness score, and Trend Radar; Google Trends and YouTube discovery need provider/API quota setup. Phase 3 adds RSS source packs, the blueprint's weighted opportunity score with explicit human inputs, and manual channel assignment; claim verification is pending a search/model provider. Phase 4 stores versioned human-authored scripts and storyboards with content hashes and a Studio editor; AI generation awaits provider configuration. Phase 5 supports user-supplied image/audio uploads with rights attestation, FFmpeg rendering, scene-level text overlays, thumbnail output, and technical container QA. It does not generate narration, source stock media, synchronize word-level captions, or fact-check editorial content. Phase 6 records human approval against exact content hashes after explicit review confirmations; YouTube OAuth, channel verification, and upload need Google credentials and are not implemented. Phase 7 imports normalized cumulative analytics CSVs and reports latest-per-video descriptive metrics with sample-size labels; live Analytics API collection and learning recommendations need real channel data and provider access. Phase 8 adds a persistent Approval Center for saved production renders and prior human decisions, authenticated media playback, and exact-hash review. A local snapshot/restore runbook is documented. Analytics emits sample-count-labeled exploratory hypotheses from imported video metrics only when at least 10 videos are present; these are explicitly non-causal and do not auto-change strategy. Per-idea workflow events record creation, version saves, render successes/failures, and human decisions transactionally; failed render attempts clean partial files and are retryable. Production render requests for identical idea/storyboard inputs serialize through a PostgreSQL advisory lock, then reuse an intact passing render or reject one that already has a human decision. Automatic retry scheduling, crash recovery, and durable checkpoints remain pending; completed attempts are capped by `AYE_MAX_PRODUCTION_ATTEMPTS`. Automated off-host backups, retention, restore drills, full service monitoring, provider/cloud cost controls, queue retries/checkpoints, and the full integration/security audit remain pending. Local render wall time and media bytes are measured, but no financial cost estimate is available.
