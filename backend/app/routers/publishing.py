from datetime import datetime
import hashlib
import json
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Approval, ContentIdea, PublishJob, RenderedVideo, StoryboardVersion, utc_now
from app.routers.approvals import _active_content_hash
from app.security import require_api_token
from app.workflows import record_workflow_event

router = APIRouter(prefix="/publishing", tags=["publishing"], dependencies=[Depends(require_api_token)])


def _lock_video_schedule(db: Session, video_id: UUID) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        digest = hashlib.sha256(f"aye:publish-schedule:{video_id}".encode("ascii")).digest()
        keys = (int.from_bytes(digest[:4], "big", signed=True), int.from_bytes(digest[4:8], "big", signed=True))
        db.execute(text("SELECT pg_advisory_xact_lock(:key1, :key2)"), {"key1": keys[0], "key2": keys[1]})


def _metadata_hash(title: str, description: str, tags: list[str]) -> str:
    canonical = json.dumps({"title": title, "description": description, "tags": tags,
                            "visibility": "private"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PublishScheduleCreate(BaseModel):
    video_id: UUID
    scheduled_at: datetime
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    metadata_reviewed: bool = False

    @field_validator("scheduled_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        normalized = [tag.strip() for tag in tags]
        if any(not tag or len(tag) > 100 for tag in normalized):
            raise ValueError("Tags must contain 1 to 100 non-whitespace characters")
        return list(dict.fromkeys(normalized))


class PublishScheduleRead(BaseModel):
    id: UUID
    video_id: UUID
    approval_id: UUID
    channel_id: UUID
    content_hash: str
    title: str
    description: str
    tags: list[str]
    metadata_hash: str | None
    metadata_reviewed_at: datetime | None
    scheduled_at: datetime
    visibility: Literal["private"]
    status: Literal["scheduled_local", "cancelled"]
    created_at: datetime
    cancelled_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


@router.get("/jobs", response_model=list[PublishScheduleRead])
def list_publish_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(PublishJob).order_by(PublishJob.scheduled_at.asc(), PublishJob.id.asc())).all()


@router.post("/jobs", response_model=PublishScheduleRead, status_code=status.HTTP_201_CREATED)
def create_publish_schedule(payload: PublishScheduleCreate, response: Response,
                            db: Session = Depends(get_db)):
    if not payload.metadata_reviewed:
        raise HTTPException(status_code=422, detail="Review and confirm the exact title, description, tags, and private visibility before saving the schedule")
    scheduled_at = payload.scheduled_at
    if scheduled_at <= utc_now():
        raise HTTPException(status_code=422, detail="Choose a future schedule time")
    video = db.get(RenderedVideo, payload.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.video_type != "production" or not video.qa_report or video.qa_report.get("status") != "TECHNICAL_QA_PASSED":
        raise HTTPException(status_code=409, detail="Only a production render with passing technical QA can be scheduled")
    idea = db.get(ContentIdea, video.content_idea_id)
    storyboard = db.get(StoryboardVersion, video.storyboard_version_id)
    if idea is None or storyboard is None:
        raise HTTPException(status_code=409, detail="Production content record is incomplete")
    approval = db.scalar(select(Approval).where(Approval.video_id == video.id).order_by(Approval.created_at.desc()).limit(1))
    if approval is None or approval.decision != "approve":
        raise HTTPException(status_code=409, detail="A human approval decision is required before scheduling")
    current_hash = _active_content_hash(video, idea, storyboard, db)
    if approval.content_hash != current_hash or video.content_hash != current_hash:
        raise HTTPException(status_code=409, detail="The human approval does not match the current content hash")

    _lock_video_schedule(db, video.id)

    title = (payload.title or idea.title).strip()
    if not title:
        raise HTTPException(status_code=422, detail="A non-empty video title is required")
    if len(title) > 100:
        raise HTTPException(status_code=422, detail="Video titles are limited to 100 characters; provide an edited title")
    metadata_hash = _metadata_hash(title, payload.description, payload.tags)
    metadata_reviewed_at = utc_now()
    existing = db.scalar(select(PublishJob).where(PublishJob.video_id == video.id))
    if existing is not None and existing.status == "scheduled_local":
        same = (existing.approval_id == approval.id and existing.content_hash == current_hash
                and existing.scheduled_at == scheduled_at and existing.title == title
                and existing.description == payload.description and existing.tags == payload.tags
                and existing.metadata_hash == metadata_hash and existing.metadata_reviewed_at is not None)
        if same:
            response.status_code = status.HTTP_200_OK
            return existing
        raise HTTPException(status_code=409, detail="This approved render already has a local schedule; cancel it before changing the schedule")
    if existing is None:
        job = PublishJob(id=uuid4(), video_id=video.id, approval_id=approval.id, channel_id=idea.channel_id,
                         content_hash=current_hash, title=title, description=payload.description,
                         tags=payload.tags, metadata_hash=metadata_hash,
                         metadata_reviewed_at=metadata_reviewed_at,
                         scheduled_at=scheduled_at, visibility="private",
                         status="scheduled_local", created_at=utc_now())
        db.add(job)
    else:
        job = existing
        job.approval_id = approval.id
        job.channel_id = idea.channel_id
        job.content_hash = current_hash
        job.title = title
        job.description = payload.description
        job.tags = payload.tags
        job.metadata_hash = metadata_hash
        job.metadata_reviewed_at = metadata_reviewed_at
        job.scheduled_at = scheduled_at
        job.visibility = "private"
        job.status = "scheduled_local"
        job.cancelled_at = None
    previous_state = idea.status
    idea.status = "SCHEDULED_LOCAL"
    record_workflow_event(db, idea.id, idea.status, "publish_scheduled_local",
                          "Human-approved render placed on the local publishing schedule; no YouTube upload was attempted",
                          {"video_id": str(video.id), "publish_job_id": str(job.id),
                           "content_hash": current_hash, "scheduled_at": scheduled_at.isoformat(),
                           "visibility": "private", "metadata_hash": metadata_hash,
                           "metadata_reviewed_at": metadata_reviewed_at.isoformat(), "upload_attempted": False},
                          previous_state=previous_state)
    db.commit()
    db.refresh(job)
    return job


@router.delete("/jobs/{job_id}", response_model=PublishScheduleRead)
def cancel_publish_schedule(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Publishing schedule not found")
    if job.status == "cancelled":
        return job
    _lock_video_schedule(db, job.video_id)
    job.status = "cancelled"
    job.cancelled_at = utc_now()
    idea = db.get(ContentIdea, db.get(RenderedVideo, job.video_id).content_idea_id)
    if idea is not None:
        previous_state = idea.status
        idea.status = "APPROVED"
        record_workflow_event(db, idea.id, idea.status, "publish_schedule_cancelled",
                              "Local publishing schedule cancelled; no YouTube upload was attempted",
                              {"video_id": str(job.video_id), "publish_job_id": str(job.id),
                               "upload_attempted": False}, previous_state=previous_state)
    db.commit()
    db.refresh(job)
    return job
