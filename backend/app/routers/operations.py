import math
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ContentIdea, MediaAsset, ProductionAttempt, RenderedVideo, WorkerHeartbeat, WorkflowEvent, utc_now
from app.security import require_api_token
from app.workflows import record_workflow_event

router = APIRouter(prefix="/operations", tags=["operations"], dependencies=[Depends(require_api_token)])


class RenderUsageSummary(BaseModel):
    period_days: int
    starts_at: datetime
    ends_at: datetime
    attempts: int
    measured_attempts: int
    unmeasured_attempts: int
    technical_qa_passes: int
    technical_qa_failures: int
    render_failures: int
    render_seconds_total: float
    render_seconds_average: float | None
    source_media_bytes: int
    rendered_video_bytes: int
    monetary_cost_available: bool = False
    note: str


class MediaIntegrityIssue(BaseModel):
    category: Literal["missing", "checksum_mismatch", "unsafe_path", "unreadable", "orphan"]
    record_type: Literal["media_asset", "video", "thumbnail", "file"]
    record_id: UUID | None = None
    storage_key: str


class MediaIntegrityReport(BaseModel):
    checked_at: datetime
    storage_root_available: bool
    referenced_files_checked: int
    issues: list[MediaIntegrityIssue]
    orphan_files_truncated: bool
    note: str


class ProductionAttemptRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    storyboard_version_id: UUID
    attempt_number: int
    status: Literal["queued", "running", "completed", "failed"]
    started_at: datetime
    finished_at: datetime | None
    video_id: UUID | None
    render_duration_seconds: float | None
    source_bytes: int | None
    output_bytes: int | None
    failure_class: str | None
    is_stale: bool
    age_seconds: int
    model_config = ConfigDict(from_attributes=True)


class WorkerHealthRead(BaseModel):
    worker_id: str
    started_at: datetime
    last_seen_at: datetime
    current_attempt_id: UUID | None
    status: Literal["online", "stale"]
    age_seconds: int


def _number(metadata: dict, key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric >= 0 else None


@router.get("/render-usage", response_model=RenderUsageSummary)
def render_usage(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    ends_at = utc_now()
    starts_at = ends_at - timedelta(days=days)
    events = db.scalars(select(WorkflowEvent).where(
        WorkflowEvent.created_at >= starts_at,
        WorkflowEvent.event_type.in_(("production_failed", "production_rendered")),
    ).order_by(WorkflowEvent.created_at.asc())).all()

    render_seconds: list[float] = []
    source_bytes = 0
    video_bytes = 0
    measured_attempts = 0
    qa_passes = 0
    qa_failures = 0
    render_failures = 0
    for event in events:
        metadata = event.metadata_json or {}
        duration = _number(metadata, "render_duration_seconds")
        source_size = _number(metadata, "source_bytes")
        output_size = _number(metadata, "output_bytes")
        if duration is not None and source_size is not None:
            measured_attempts += 1
            render_seconds.append(duration)
            source_bytes += int(source_size)
        if output_size is not None:
            video_bytes += int(output_size)
        if event.event_type == "production_failed":
            render_failures += 1
        else:
            outcome = metadata.get("technical_qa_status")
            if outcome == "TECHNICAL_QA_PASSED":
                qa_passes += 1
            elif outcome == "TECHNICAL_QA_FAILED":
                qa_failures += 1

    attempts = len(events)
    total_seconds = round(sum(render_seconds), 3)
    return RenderUsageSummary(
        period_days=days, starts_at=starts_at, ends_at=ends_at,
        attempts=attempts, measured_attempts=measured_attempts,
        unmeasured_attempts=attempts - measured_attempts,
        technical_qa_passes=qa_passes, technical_qa_failures=qa_failures,
        render_failures=render_failures, render_seconds_total=total_seconds,
        render_seconds_average=round(total_seconds / measured_attempts, 3) if measured_attempts else None,
        source_media_bytes=source_bytes, rendered_video_bytes=video_bytes,
        note="Shows local render time and media volume from recorded events. No provider/API spend or rupee cost is configured, so financial cost is unavailable.",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@router.get("/media-integrity", response_model=MediaIntegrityReport)
def media_integrity(db: Session = Depends(get_db)):
    """Read-only audit of database-referenced files against local media storage."""
    root = Path(get_settings().media_dir).resolve()
    issues: list[MediaIntegrityIssue] = []
    referenced_keys: set[str] = set()
    checked = 0

    def inspect(storage_key: str, record_type: Literal["media_asset", "video", "thumbnail"],
                record_id: UUID | None, checksum: str | None = None) -> None:
        nonlocal checked
        referenced_keys.add(storage_key)
        path = (root / storage_key).resolve()
        if path.parent != root:
            issues.append(MediaIntegrityIssue(category="unsafe_path", record_type=record_type,
                                              record_id=record_id, storage_key=storage_key))
            return
        if not path.is_file():
            issues.append(MediaIntegrityIssue(category="missing", record_type=record_type,
                                              record_id=record_id, storage_key=storage_key))
            return
        checked += 1
        if checksum is not None:
            try:
                matches = _sha256(path) == checksum
            except OSError:
                issues.append(MediaIntegrityIssue(category="unreadable", record_type=record_type,
                                                  record_id=record_id, storage_key=storage_key))
                return
            if not matches:
                issues.append(MediaIntegrityIssue(category="checksum_mismatch", record_type=record_type,
                                                  record_id=record_id, storage_key=storage_key))

    for asset in db.scalars(select(MediaAsset)).all():
        inspect(asset.storage_key, "media_asset", asset.id, asset.checksum)
    for video in db.scalars(select(RenderedVideo)).all():
        inspect(video.storage_key, "video", video.id, video.checksum)
        if video.thumbnail_key:
            inspect(video.thumbnail_key, "thumbnail", video.id)

    orphan_files: list[str] = []
    orphan_count = 0
    if root.is_dir():
        for path in root.iterdir():
            if path.is_file() and path.name not in referenced_keys:
                orphan_count += 1
                if orphan_count <= 100:
                    orphan_files.append(path.name)
    truncated = orphan_count > 100
    issues.extend(MediaIntegrityIssue(category="orphan", record_type="file", storage_key=key)
                  for key in orphan_files)

    return MediaIntegrityReport(
        checked_at=utc_now(), storage_root_available=root.is_dir(),
        referenced_files_checked=checked, issues=issues,
        orphan_files_truncated=truncated,
        note="Read-only local filesystem check. A clean report does not replace paired database and media backups.",
    )


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _attempt_read(attempt: ProductionAttempt, now: datetime, stale_after: int) -> ProductionAttemptRead:
    age = max(0, int((now - _aware_utc(attempt.started_at)).total_seconds()))
    return ProductionAttemptRead(
        id=attempt.id, content_idea_id=attempt.content_idea_id,
        storyboard_version_id=attempt.storyboard_version_id,
        attempt_number=attempt.attempt_number, status=attempt.status,
        started_at=attempt.started_at, finished_at=attempt.finished_at,
        video_id=attempt.video_id, render_duration_seconds=attempt.render_duration_seconds,
        source_bytes=attempt.source_bytes, output_bytes=attempt.output_bytes,
        failure_class=attempt.failure_class,
        is_stale=attempt.status in ("queued", "running") and age >= stale_after,
        age_seconds=age,
    )


@router.get("/production-attempts", response_model=list[ProductionAttemptRead])
def list_production_attempts(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    settings = get_settings()
    attempts = db.scalars(select(ProductionAttempt).order_by(ProductionAttempt.started_at.desc()).limit(limit)).all()
    now = utc_now()
    return [_attempt_read(attempt, now, settings.production_stale_after_seconds) for attempt in attempts]


@router.get("/workers", response_model=list[WorkerHealthRead])
def list_workers(db: Session = Depends(get_db)):
    workers = db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()).limit(100)).all()
    now = utc_now()
    live_window = max(30, int(get_settings().worker_poll_seconds * 3))
    result = []
    for worker in workers:
        age = max(0, int((now - _aware_utc(worker.last_seen_at)).total_seconds()))
        result.append(WorkerHealthRead(
            worker_id=worker.worker_id, started_at=worker.started_at,
            last_seen_at=worker.last_seen_at, current_attempt_id=worker.current_attempt_id,
            status="online" if age <= live_window else "stale", age_seconds=age,
        ))
    return result


@router.get("/production-attempts/{attempt_id}", response_model=ProductionAttemptRead)
def get_production_attempt(attempt_id: UUID, db: Session = Depends(get_db)):
    attempt = db.get(ProductionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Production attempt not found")
    settings = get_settings()
    return _attempt_read(attempt, utc_now(), settings.production_stale_after_seconds)


@router.post("/production-attempts/{attempt_id}/recover", response_model=ProductionAttemptRead)
def recover_production_attempt(attempt_id: UUID, db: Session = Depends(get_db)):
    attempt = db.scalar(select(ProductionAttempt).where(ProductionAttempt.id == attempt_id).with_for_update())
    if attempt is None:
        raise HTTPException(status_code=404, detail="Production attempt not found")
    settings = get_settings()
    if attempt.status not in ("queued", "running") and attempt.failure_class in ("interrupted", "queue_timeout"):
        return _attempt_read(attempt, utc_now(), settings.production_stale_after_seconds)
    if attempt.status not in ("queued", "running"):
        raise HTTPException(status_code=409, detail="Only a queued or running production attempt can be recovered")
    interrupted_status = attempt.status
    now = utc_now()
    started_at = _aware_utc(attempt.started_at)
    age_seconds = max(0, int((now - started_at).total_seconds()))
    if age_seconds < settings.production_stale_after_seconds:
        raise HTTPException(status_code=409,
                            detail=f"Attempt is {age_seconds}s old; recovery is allowed after {settings.production_stale_after_seconds}s")

    media_root = Path(settings.media_dir).resolve()
    cleanup_succeeded = True
    for key in (f"{attempt.id}.mp4", f"{attempt.id}-thumb.jpg"):
        path = media_root / key
        if path.parent.resolve() != media_root:
            cleanup_succeeded = False
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            cleanup_succeeded = False

    idea = db.get(ContentIdea, attempt.content_idea_id)
    if idea is None:
        raise HTTPException(status_code=409, detail="The content idea for this attempt no longer exists")
    previous_state = idea.status
    idea.status = "PRODUCTION_FAILED"
    attempt.status = "failed"
    attempt.finished_at = now
    attempt.render_duration_seconds = round((now - started_at).total_seconds(), 3) if interrupted_status == "running" else None
    failure_class = "interrupted" if interrupted_status == "running" else "queue_timeout"
    attempt.failure_class = failure_class
    record_workflow_event(db, idea.id, idea.status, "production_failed",
                          ("Stale production attempt was recovered as interrupted; inspect the storyboard and media before retrying"
                           if failure_class == "interrupted" else "Stale queued production attempt was recovered after the worker failed to claim it"),
                          {"storyboard_version_id": str(attempt.storyboard_version_id),
                           "attempt_number": attempt.attempt_number,
                           "attempt_id": str(attempt.id),
                           "render_duration_seconds": attempt.render_duration_seconds,
                           "source_bytes": attempt.source_bytes,
                           "partial_output_cleanup_succeeded": cleanup_succeeded,
                           "failure_class": failure_class},
                          previous_state=previous_state, actor="local-owner")
    db.commit()
    db.refresh(attempt)
    return _attempt_read(attempt, now, settings.production_stale_after_seconds)
