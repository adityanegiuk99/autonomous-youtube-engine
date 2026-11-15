# Local operations and recovery

This runbook covers the current Docker Compose development stack. It is not a production deployment guide. The Compose database credentials are development-only, the API token is single-owner, and the stack binds to loopback.

## What must be backed up together

- PostgreSQL contains channel, idea, version, render, approval, analytics, and workflow/operations event records.
- The `aye_media` Docker volume contains uploaded source assets and rendered videos/thumbnails. Database rows refer to files in this volume.
- Keep the database dump and media archive from the same maintenance window. Restoring only one can leave missing files or orphaned files.
- Keep the `.env` API token and trusted feed configuration in a separate secrets store. Do not put `.env` in the backup archive or Git.

## Create a local snapshot

These examples use Bash (including WSL Bash) and assume the Compose services are running. Use a protected backup directory with enough free space. Stop the worker, API, and dashboard before taking the paired database and media snapshots so no process changes either side of the backup set.

```bash
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose stop worker api web
docker compose exec -T db pg_dump -U aye -d aye -Fc > "backups/aye-db-${stamp}.dump"
docker compose run --rm -T --no-deps --entrypoint tar api -czf - -C /data/media . > "backups/aye-media-${stamp}.tar.gz"
docker compose start api worker web
```

Check that both files are non-empty and record their hashes in the protected backup location:

```bash
test -s "backups/aye-db-${stamp}.dump" && test -s "backups/aye-media-${stamp}.tar.gz"
sha256sum "backups/aye-db-${stamp}.dump" "backups/aye-media-${stamp}.tar.gz"
```

If snapshot creation fails, restart `api`, `worker`, and `web` before investigating. Protect backups as sensitive data: media and database records may contain unpublished content and personal notes.

## Restore a snapshot

Restoring replaces current data. First preserve a fresh snapshot of the current installation if it may be needed. Confirm the chosen database dump and media archive share the same timestamp. Stop the worker, dashboard, and API, then restore into the existing `aye` database and media volume:

```bash
docker compose stop worker api web
docker compose exec -T db pg_restore -U aye -d aye --clean --if-exists < backups/aye-db-YYYYMMDDTHHMMSSZ.dump
docker compose run --rm -T --no-deps --entrypoint sh api -c 'find /data/media -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf - -C /data/media' < backups/aye-media-YYYYMMDDTHHMMSSZ.tar.gz
docker compose start api worker web
```

After restore, check `http://localhost:8000/api/v1/health`, connect to the dashboard with the configured API token, inspect the Approval Center, and open a restored render and thumbnail. A database rollback does not roll back files by itself. Avoid `docker compose down -v`: it deletes the named database and media volumes.

## Schema changes and recovery limits

The API container applies Alembic migrations at startup. Before updating an installation, stop the worker while taking a paired database/media snapshot and keep the previous application image available until the updated stack is confirmed. This repository does not yet automate off-machine backups, retention, encryption, scheduled restore drills, full service monitoring, or disaster recovery. Local Docker volumes are not a backup until copied off the host and restore-checked.

## Inspect local media integrity

The Operations page offers a read-only media audit at `GET /api/v1/operations/media-integrity`. It checks that database-referenced source assets, rendered videos, thumbnails, and generated caption sidecars exist under the configured media directory; it compares checksums where the database stores them. It also lists up to 100 unreferenced files. The audit does not delete or repair anything. Review orphan entries before manual cleanup, since interrupted operations may leave files that still matter to an operator. Run it after a restore or storage move, then open important renders in the Approval Center.

## Background production worker

Docker Compose runs a separate `worker` service. The API healthcheck waits for its health endpoint, which is available after startup migrations, before Compose starts the worker. Studio queues a production attempt in PostgreSQL and polls its durable status; the worker claims queued rows with row locking so worker replicas cannot claim the same attempt. `AYE_WORKER_POLL_SECONDS` controls the idle poll interval. API and worker share the `aye_media` volume. Operations displays durable worker heartbeat records and the last reported active attempt. A stale heartbeat means the worker has not updated its status recently; it does not prove why the process stopped. The worker also checks database schema startup, but does not provide automatic retries or resumable FFmpeg checkpoints. A stopped worker can leave queued attempts unclaimed; Operations marks queued and running attempts stale after the configured timeout.

## Local publishing schedule

The Publishing page can save and cancel private-only schedule records for an exact, currently approved render. Saving requires a separate human confirmation of the exact title, description, tags, and visibility; the API records a canonical metadata hash and review time. This attestation is in addition to video approval, and any metadata edit requires a new review. The page does not upload or publish content. Cancelling a local entry does not undo an external action because none is attempted. Configure Google OAuth and implement resumable upload and recovery before treating any item as YouTube-scheduled.

## Recover an interrupted production render

Production render attempts are committed before FFmpeg starts. If the worker exits mid-render, the Operations page shows the attempt as running. A queued attempt older than the same threshold indicates that no worker claimed it. Once either state is older than `AYE_PRODUCTION_STALE_AFTER_SECONDS` (six hours by default), an operator can recover it after checking worker health. Recovery marks it failed and removes its attempt-specific MP4 and thumbnail when possible. It does not resume FFmpeg from a checkpoint. The recovered attempt counts against `AYE_MAX_PRODUCTION_ATTEMPTS`; inspect the source files and rendering configuration before retrying. If cleanup fails, use the media integrity audit to inspect leftover files.
