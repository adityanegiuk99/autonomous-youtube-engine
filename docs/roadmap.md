# AYE Implementation Roadmap

The attached product blueprint defines the destination. This repository starts with no application implementation, so work proceeds in vertical slices and avoids representing planned integrations as operational.

| Phase | Deliverable | Status |
|---|---|---|
| 1. Foundation | FastAPI, Next.js shell, PostgreSQL development service, configuration, channel management | In progress |
| 2. Trend intelligence | RSS/provider adapters, normalization, deduplication, scoring, Trend Radar | Not started |
| 3. Research and strategy | sourced dossiers, claim extraction, opportunity scoring and routing | Not started |
| 4. Content generation | versioned scripts, formats, storyboard editor | Not started |
| 5. Video production | voice, licensed visuals, FFmpeg, captions, thumbnails, QA | Not started |
| 6. Publishing | OAuth, channel verification, human approval, resumable private-first upload | Not started |
| 7. Analytics and learning | snapshots, comparisons, evidence-backed recommendations | Not started |
| 8. Integration audit | operational security, recovery, costs, integration verification | Not started |

## Phase 1 exit criteria

- Local services can be configured without committing secrets.
- API and dashboard have a clear, working foundation.
- Channel configuration CRUD persists records and does not imply OAuth connection.
- Database schema changes have a migration path.
- README explains setup and current limitations.

The requested implementation in this pass begins Phase 1. It is not the complete MVP and does not implement discovery, generation, media rendering, OAuth, publishing, or analytics.
