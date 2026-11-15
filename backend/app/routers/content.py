import hashlib
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContentIdea, ScriptVersion, StoryboardVersion, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/ideas", tags=["content"], dependencies=[Depends(require_api_token)])


class ScriptCreate(BaseModel):
    body: str = Field(min_length=1, max_length=100_000)
    origin: str = Field(default="human", pattern="^human$")


class ScriptRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    version: int
    body: str
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
    version = (db.scalar(select(func.max(ScriptVersion.version)).where(ScriptVersion.content_idea_id == idea_id)) or 0) + 1
    content_hash = hashlib.sha256(payload.body.encode("utf-8")).hexdigest()
    script = ScriptVersion(content_idea_id=idea_id, version=version, body=payload.body,
                           content_hash=content_hash, origin=payload.origin, created_at=utc_now())
    db.add(script)
    idea.status = "SCRIPT_READY"
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
    version = (db.scalar(select(func.max(StoryboardVersion.version)).where(StoryboardVersion.content_idea_id == idea_id)) or 0) + 1
    scenes = [scene.model_dump() for scene in payload.scenes]
    serialized = json.dumps(scenes, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    storyboard = StoryboardVersion(content_idea_id=idea_id, script_version_id=script.id, version=version,
                                   scenes=scenes, content_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                                   created_at=utc_now())
    db.add(storyboard)
    idea.status = "STORYBOARD_READY"
    db.commit()
    db.refresh(storyboard)
    return storyboard
