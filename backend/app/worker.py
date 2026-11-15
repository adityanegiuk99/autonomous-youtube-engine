"""PostgreSQL-backed production queue worker."""

import logging
import time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database import SessionLocal
from app.models import ContentIdea, ProductionAttempt, utc_now
from app.production.jobs import _cleanup_attempt, execute_production_attempt, fail_attempt, load_production_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("aye.worker")


def _wait_for_schema() -> None:
    while True:
        try:
            with SessionLocal() as db:
                db.execute(select(ProductionAttempt.id).limit(1)).first()
            return
        except SQLAlchemyError:
            logger.info("Database schema is not ready; retrying")
            time.sleep(2)


def run_one() -> bool:
    """Claim and execute one queued render; PostgreSQL SKIP LOCKED permits replicas."""
    with SessionLocal() as db:
        attempt = db.scalar(
            select(ProductionAttempt)
            .where(ProductionAttempt.status == "queued")
            .order_by(ProductionAttempt.started_at.asc(), ProductionAttempt.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if attempt is None:
            return False
        attempt.status = "running"
        attempt.started_at = utc_now()
        db.commit()
        attempt_id = attempt.id
        idea_id = attempt.content_idea_id
        storyboard_id = attempt.storyboard_version_id

    with SessionLocal() as db:
        attempt = db.get(ProductionAttempt, attempt_id)
        if attempt is None or attempt.status != "running":
            return True
        idea = db.get(ContentIdea, idea_id)
        try:
            context = load_production_context(db, idea_id, storyboard_id)
        except HTTPException:
            if idea is not None:
                cleanup = _cleanup_attempt(Path(get_settings().media_dir).resolve(), attempt_id)
                fail_attempt(db, attempt, idea, "preflight_validation", cleanup)
                db.commit()
            else:
                attempt.status = "failed"
                attempt.finished_at = utc_now()
                attempt.failure_class = "missing_content"
                db.commit()
            logger.warning("Queued attempt %s failed its preflight checks", attempt_id)
            return True

        video, error = execute_production_attempt(db, attempt, context)
        if error:
            logger.warning("Queued attempt %s failed during media rendering", attempt_id)
        elif video is not None:
            logger.info("Queued attempt %s completed as video %s", attempt_id, video.id)
    return True


def main() -> None:
    _wait_for_schema()
    settings = get_settings()
    logger.info("Production queue worker started; polling every %.1fs", settings.worker_poll_seconds)
    while True:
        try:
            if not run_one():
                time.sleep(settings.worker_poll_seconds)
        except Exception:
            logger.exception("Unexpected worker error; active attempt remains visible for recovery")
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
