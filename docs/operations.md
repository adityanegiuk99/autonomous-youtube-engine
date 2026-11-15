# Local operations and recovery

This runbook covers the current Docker Compose development stack. It is not a production deployment guide. The Compose database credentials are development-only, the API token is single-owner, and the stack binds to loopback.

## What must be backed up together

- PostgreSQL contains channel, idea, version, render, approval, analytics, and workflow/operations event records.
- The `aye_media` Docker volume contains uploaded source assets and rendered videos/thumbnails. Database rows refer to files in this volume.
- Keep the database dump and media archive from the same maintenance window. Restoring only one can leave missing files or orphaned files.
- Keep the `.env` API token and trusted feed configuration in a separate secrets store. Do not put `.env` in the backup archive or Git.

## Create a local snapshot

These examples use Bash (including WSL Bash) and assume the Compose services are running. Use a protected backup directory with enough free space. `docker compose stop api web` pauses writes while the matching database and media snapshots are created; restart the services when finished.

```bash
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose stop api web
docker compose exec -T db pg_dump -U aye -d aye -Fc > "backups/aye-db-${stamp}.dump"
docker compose run --rm -T --no-deps --entrypoint tar api -czf - -C /data/media . > "backups/aye-media-${stamp}.tar.gz"
docker compose start api web
```

Check that both files are non-empty and record their hashes in the protected backup location:

```bash
test -s "backups/aye-db-${stamp}.dump" && test -s "backups/aye-media-${stamp}.tar.gz"
sha256sum "backups/aye-db-${stamp}.dump" "backups/aye-media-${stamp}.tar.gz"
```

If snapshot creation fails, restart `api` and `web` before investigating. Protect backups as sensitive data: media and database records may contain unpublished content and personal notes.

## Restore a snapshot

Restoring replaces current data. First preserve a fresh snapshot of the current installation if it may be needed. Confirm the chosen database dump and media archive share the same timestamp. Stop the dashboard and API, then restore into the existing `aye` database and media volume:

```bash
docker compose stop api web
docker compose exec -T db pg_restore -U aye -d aye --clean --if-exists < backups/aye-db-YYYYMMDDTHHMMSSZ.dump
docker compose run --rm -T --no-deps --entrypoint sh api -c 'find /data/media -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf - -C /data/media' < backups/aye-media-YYYYMMDDTHHMMSSZ.tar.gz
docker compose start api web
```

After restore, check `http://localhost:8000/api/v1/health`, connect to the dashboard with the configured API token, inspect the Approval Center, and open a restored render and thumbnail. A database rollback does not roll back files by itself. Avoid `docker compose down -v`: it deletes the named database and media volumes.

## Schema changes and recovery limits

The API container applies Alembic migrations at startup. Before updating an installation, create a paired database/media snapshot and keep the previous application image available until the updated stack is confirmed. This repository does not yet automate off-machine backups, retention, encryption, scheduled restore drills, monitoring, or disaster recovery. Local Docker volumes are not a backup until copied off the host and restore-checked.
