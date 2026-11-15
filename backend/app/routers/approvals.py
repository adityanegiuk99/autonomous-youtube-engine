import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.content_hashing import production_content_hash
from app.database import get_db
from app.models import Approval, ContentIdea, MediaAsset, RenderedVideo, ScriptVersion, StoryboardVersion, utc_now
from app.security import require_api_token
from app.workflows import record_workflow_event

router = APIRouter(prefix="/videos", tags=["approvals"], dependencies=[Depends(require_api_token)])


class ReviewChecks(BaseModel):
    editorial_accuracy_reviewed: bool = False
    sources_reviewed: bool = False
    media_rights_reviewed: bool = False
    disclosures_reviewed: bool = False


class ApprovalCreate(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    review_checks: ReviewChecks = Field(default_factory=ReviewChecks)
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def decision_requires_notes(self):
        if self.decision != "approve" and not (self.notes or "").strip():
            raise ValueError("Notes are required when rejecting or requesting changes")
        if self.decision == "approve" and not all(self.review_checks.model_dump().values()):
            raise ValueError("Review every approval item before approving")
        return self


class ApprovalRead(BaseModel):
    id: UUID
    video_id: UUID
    content_hash: str
    reviewer: str
    decision: str
    review_checks: dict
    notes: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


def _active_content_hash(video: RenderedVideo, idea: ContentIdea, storyboard: StoryboardVersion,
                         db: Session) -> str:
    latest_board = db.scalar(select(func.max(StoryboardVersion.version)).where(StoryboardVersion.content_idea_id == idea.id))
    latest_script = db.scalar(select(func.max(ScriptVersion.version)).where(ScriptVersion.content_idea_id == idea.id))
    script = db.get(ScriptVersion, storyboard.script_version_id)
    if latest_board != storyboard.version or script is None or script.version != latest_script:
        raise HTTPException(status_code=409, detail="A newer script or storyboard exists; render and review the latest version")
    if not video.storage_key or not video.checksum:
        raise HTTPException(status_code=409, detail="Rendered file metadata is incomplete")
    media_root = Path(get_settings().media_dir).resolve()
    path = (media_root / video.storage_key).resolve()
    if path.parent != media_root or not path.is_file():
        raise HTTPException(status_code=409, detail="Rendered file is missing")
    digest = hashlib.sha256()
    with path.open("rb") as rendered:
        for chunk in iter(lambda: rendered.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != video.checksum:
        raise HTTPException(status_code=409, detail="Rendered file changed after technical QA")
    if video.captions_key:
        if not video.captions_checksum:
            raise HTTPException(status_code=409, detail="Caption file metadata is incomplete")
        captions_path = (media_root / video.captions_key).resolve()
        if captions_path.parent != media_root or not captions_path.is_file():
            raise HTTPException(status_code=409, detail="Caption file is missing")
        caption_digest = hashlib.sha256()
        with captions_path.open("rb") as captions_file:
            for chunk in iter(lambda: captions_file.read(1024 * 1024), b""):
                caption_digest.update(chunk)
        if caption_digest.hexdigest() != video.captions_checksum:
            raise HTTPException(status_code=409, detail="Caption file changed after technical QA")

    asset_ids = {UUID(str(scene[field])) for scene in storyboard.scenes for field in ("image_asset_id", "audio_asset_id") if scene.get(field)}
    assets = db.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids))).all() if asset_ids else []
    if len(assets) != len(asset_ids):
        raise HTTPException(status_code=409, detail="A reviewed media asset is missing")
    for asset in assets:
        media_path = (media_root / asset.storage_key).resolve()
        if media_path.parent != media_root or not media_path.is_file():
            raise HTTPException(status_code=409, detail="A reviewed source media file is missing")
        media_digest = hashlib.sha256()
        with media_path.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                media_digest.update(chunk)
        if media_digest.hexdigest() != asset.checksum:
            raise HTTPException(status_code=409, detail="A source media file changed after upload")
    manifest = [{"asset_id": str(asset.id), "asset_type": asset.asset_type, "license_type": asset.license_type,
                 "source_url": asset.source_url, "checksum": asset.checksum, "rights_confirmed": asset.rights_confirmed}
                for asset in assets]
    current = production_content_hash(idea, script, storyboard, manifest, video.checksum)
    if video.content_hash != current:
        raise HTTPException(status_code=409, detail="Content changed after rendering; create a fresh production render")
    return current


@router.get("/{video_id}/approvals", response_model=list[ApprovalRead])
def list_approvals(video_id: UUID, db: Session = Depends(get_db)):
    if db.get(RenderedVideo, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return db.scalars(select(Approval).where(Approval.video_id == video_id).order_by(Approval.created_at.desc())).all()


@router.post("/{video_id}/approvals", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
def create_approval(video_id: UUID, payload: ApprovalCreate, reviewer: str = Depends(require_api_token),
                    db: Session = Depends(get_db)):
    video = db.get(RenderedVideo, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.video_type != "production" or not video.qa_report or video.qa_report.get("status") != "TECHNICAL_QA_PASSED":
        raise HTTPException(status_code=409, detail="Only a production render with passing technical QA can be reviewed for approval")
    idea = db.get(ContentIdea, video.content_idea_id)
    storyboard = db.get(StoryboardVersion, video.storyboard_version_id)
    if idea is None or storyboard is None:
        raise HTTPException(status_code=409, detail="Production content record is incomplete")
    current_hash = _active_content_hash(video, idea, storyboard, db)
    previous = db.scalar(select(Approval).where(Approval.video_id == video_id).order_by(Approval.created_at.desc()).limit(1))
    if previous is not None:
        same_decision = (previous.content_hash == current_hash and previous.decision == payload.decision
                         and previous.review_checks == payload.review_checks.model_dump() and previous.notes == payload.notes)
        if same_decision:
            return previous
        raise HTTPException(status_code=409, detail="This render already has a final human decision; revise the content and render a new version")
    approval = Approval(video_id=video.id, content_hash=current_hash, reviewer=reviewer,
                        decision=payload.decision, review_checks=payload.review_checks.model_dump(),
                        notes=payload.notes, created_at=utc_now())
    db.add(approval)
    previous_state = idea.status
    video.status = {"approve": "APPROVED", "reject": "REJECTED", "request_changes": "CHANGES_REQUESTED"}[payload.decision]
    idea.status = video.status
    record_workflow_event(db, idea.id, idea.status, "approval_decision",
                          f"Human reviewer recorded {payload.decision}",
                          {"video_id": str(video.id), "content_hash": current_hash,
                           "decision": payload.decision}, previous_state=previous_state)
    db.commit()
    db.refresh(approval)
    return approval
