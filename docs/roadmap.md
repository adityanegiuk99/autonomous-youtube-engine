# AYE Implementation Roadmap

The attached product blueprint defines the destination. This repository starts with no application implementation, so work proceeds in vertical slices and avoids representing planned integrations as operational.

| Phase | Deliverable | Status |
|---|---|---|
| 1. Foundation | FastAPI, Next.js shell, PostgreSQL development service, configuration, channel management | Partial: local bearer token and channel CRUD UI; multi-user identity remains |
| 2. Trend intelligence | RSS/provider adapters, normalization, deduplication, scoring, Trend Radar | In progress: RSS adapter and UI |
| 3. Research and strategy | sourced dossiers, claim extraction, opportunity scoring and routing | Partial: RSS source packs, opportunity scoring, manual channel routing; claim verification pending provider |
| 4. Content generation | versioned scripts, formats, storyboard editor | Partial: versioned human script/storyboard API and Studio UI; AI generation pending provider |
| 5. Video production | voice, licensed visuals, FFmpeg, captions, thumbnails, QA | Partial: silent FFmpeg animatic preview |
| 6. Publishing | OAuth, channel verification, human approval, resumable private-first upload | Not started |
| 7. Analytics and learning | snapshots, comparisons, evidence-backed recommendations | Not started |
| 8. Integration audit | operational security, recovery, costs, integration verification | Not started |

## Phase 1 exit criteria

- Local services can be configured without committing secrets.
- API and dashboard have a clear, working foundation.
- Channel configuration CRUD persists records and does not imply OAuth connection.
- Database schema changes have a migration path.
- README explains setup and current limitations.

Phase 1 has a working local bearer-token gate and channel CRUD UI, but lacks multi-user identity. Phase 2 has RSS ingestion, deduplication, a source-diversity/freshness score, and Trend Radar; Google Trends and YouTube discovery need provider/API quota setup. Phase 3 adds RSS source packs, the blueprint's weighted opportunity score with explicit human inputs, and manual channel assignment; claim verification is pending a search/model provider. Phase 4 stores versioned human-authored scripts and storyboards with content hashes and a Studio editor; AI generation awaits provider configuration. Phase 5 renders silent storyboard animatics; TTS, licensed visuals, captions, thumbnails, and production QA remain unimplemented. Phase 6 publishing and later analytics require Google OAuth and user credentials; no external publish action is implemented.
