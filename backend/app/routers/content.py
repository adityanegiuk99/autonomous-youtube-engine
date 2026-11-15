import hashlib
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContentIdea, MediaAsset, ResearchDocument, ScriptVersion, StoryboardVersion, utc_now
from app.security import require_api_token
from app.workflows import record_workflow_event

router = APIRouter(prefix="/ideas", tags=["content"], dependencies=[Depends(require_api_token)])
MAX_RESEARCH_SNAPSHOT_BYTES = 500_000


class ScriptCreate(BaseModel):
    body: str = Field(min_length=1, max_length=100_000)
    origin: str = Field(default="human", pattern="^human$")
    research_document_ids: list[UUID] = Field(default_factory=list, max_length=20)


class ScriptRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    version: int
    body: str
    source_references: list[dict]
    content_hash: str
    origin: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class Scene(BaseModel):
    duration_seconds: float = Field(gt=0, le=180)
    voiceover: str = Field(min_length=1, max_length=5000)
    visual_description: str = Field(min_length=1, max_length=2000)
    asset_type: str = Field(default="user_supplied", max_length=40)
    transition: str = Field(default="cut", max_length=40)
    subtitle: str = Field(default="", max_length=2000)
    image_asset_id: UUID | None = None
    audio_asset_id: UUID | None = None
    source_attribution: list[str] = Field(default_factory=list, max_length=20)


class StoryboardCreate(BaseModel):
    script_version_id: UUID
    scenes: list[Scene] = Field(min_length=1, max_length=200)


class StoryboardRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    script_version_id: UUID
    version: int
    scenes: list[dict]
    content_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("/{idea_id}/scripts", response_model=list[ScriptRead])
def list_scripts(idea_id: UUID, db: Session = Depends(get_db)):
    if db.get(ContentIdea, idea_id) is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    return db.scalars(select(ScriptVersion).where(ScriptVersion.content_idea_id == idea_id).order_by(ScriptVersion.version.desc())).all()


@router.post("/{idea_id}/scripts", response_model=ScriptRead, status_code=status.HTTP_201_CREATED)
def create_script(idea_id: UUID, payload: ScriptCreate, db: Session = Depends(get_db)):
    idea = db.scalar(select(ContentIdea).where(ContentIdea.id == idea_id).with_for_update())
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    if payload.research_document_ids and idea.trend_item_id is None:
        raise HTTPException(status_code=422, detail="Research dossiers can only be linked to ideas with a trend item")
    source_references: list[dict] = []
    if payload.research_document_ids:
        if len(set(payload.research_document_ids)) != len(payload.research_document_ids):
            raise HTTPException(status_code=422, detail="Research dossier IDs must be unique")
        documents = db.scalars(select(ResearchDocument).where(
            ResearchDocument.id.in_(payload.research_document_ids),
            ResearchDocument.trend_item_id == idea.trend_item_id,
            ResearchDocument.document_type == "manual_research_dossier",
        )).all()
        by_id = {document.id: document for document in documents}
        if len(by_id) != len(payload.research_document_ids):
            raise HTTPException(status_code=422, detail="Every linked dossier must belong to the idea's trend and be a manual research dossier")
        source_references = [
            {"research_document_id": str(document.id), "version": document.version,
             "content_hash": document.content_hash, "content": document.content}
            for document in (by_id[document_id] for document_id in payload.research_document_ids)
        ]
        if len(json.dumps(source_references, separators=(",", ":"), ensure_ascii=False).encode("utf-8")) > MAX_RESEARCH_SNAPSHOT_BYTES:
            raise HTTPException(status_code=413, detail="Selected dossier snapshots exceed 500 KB; select fewer or smaller dossiers")
    version = (db.scalar(select(func.max(ScriptVersion.version)).where(ScriptVersion.content_idea_id == idea_id)) or 0) + 1
    hash_payload = json.dumps({"body": payload.body, "source_references": source_references},
                              sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    content_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()
    script = ScriptVersion(content_idea_id=idea_id, version=version, body=payload.body,
                           source_references=source_references, content_hash=content_hash,
                           origin=payload.origin, created_at=utc_now())
    db.add(script)
    db.flush()
    previous_state = idea.status
    idea.status = "SCRIPT_READY"
    record_workflow_event(db, idea.id, idea.status, "script_saved", "Human-authored script version saved",
                          {"script_version_id": str(script.id), "version": version,
                           "content_hash": content_hash,
                           "research_document_ids": [item["research_document_id"] for item in source_references]},
                          previous_state=previous_state)
    db.commit()
    db.refresh(script)
    return script


@router.get("/{idea_id}/storyboards", response_model=list[StoryboardRead])
def list_storyboards(idea_id: UUID, db: Session = Depends(get_db)):
    if db.get(ContentIdea, idea_id) is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    return db.scalars(select(StoryboardVersion).where(StoryboardVersion.content_idea_id == idea_id).order_by(StoryboardVersion.version.desc())).all()


@router.post("/{idea_id}/storyboards", response_model=StoryboardRead, status_code=status.HTTP_201_CREATED)
def create_storyboard(idea_id: UUID, payload: StoryboardCreate, db: Session = Depends(get_db)):
    idea = db.scalar(select(ContentIdea).where(ContentIdea.id == idea_id).with_for_update())
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    script = db.get(ScriptVersion, payload.script_version_id)
    if script is None or script.content_idea_id != idea_id:
        raise HTTPException(status_code=404, detail="Script version not found for this idea")
    scenes = [scene.model_dump() for scene in payload.scenes]
    asset_ids = {asset_id for scene in scenes for asset_id in (scene["image_asset_id"], scene["audio_asset_id"]) if asset_id}
    assets = {asset.id: asset for asset in db.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids))).all()} if asset_ids else {}
    for scene in scenes:
        for field, expected_type in (("image_asset_id", "image"), ("audio_asset_id", "audio")):
            asset_id = scene[field]
            if asset_id is None:
                continue
            asset = assets.get(asset_id)
            if asset is None or asset.asset_type != expected_type or not asset.rights_confirmed:
                raise HTTPException(status_code=422, detail=f"{field} must reference an uploaded, rights-confirmed {expected_type} asset")
            if asset.license_type != "owned" and not scene["source_attribution"]:
                raise HTTPException(status_code=422, detail="Add source attribution for non-owned media")
    version = (db.scalar(select(func.max(StoryboardVersion.version)).where(StoryboardVersion.content_idea_id == idea_id)) or 0) + 1
    serialized = json.dumps(scenes, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    storyboard = StoryboardVersion(content_idea_id=idea_id, script_version_id=script.id, version=version,
                                   scenes=scenes, content_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                                   created_at=utc_now())
    db.add(storyboard)
    db.flush()
    previous_state = idea.status
    idea.status = "STORYBOARD_READY"
    record_workflow_event(db, idea.id, idea.status, "storyboard_saved", "Storyboard version saved",
                          {"storyboard_version_id": str(storyboard.id), "version": version,
                           "script_version_id": str(script.id), "content_hash": storyboard.content_hash},
                          previous_state=previous_state)
    db.commit()
    db.refresh(storyboard)
    return storyboard
