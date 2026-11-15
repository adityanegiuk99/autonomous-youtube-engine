from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import ContentIdea, RenderedVideo, StoryboardVersion, utc_now
from app.production.preview import render_silent_preview
from app.security import require_api_token

router = APIRouter(tags=["videos"], dependencies=[Depends(require_api_token)])


class VideoRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    storyboard_version_id: UUID
    checksum: str
    duration_seconds: float
    width: int
    height: int
    status: str
    created_at: datetime
    preview_url: str = ""
    model_config = ConfigDict(from_attributes=True)


@router.post("/ideas/{idea_id}/render-preview", response_model=VideoRead, status_code=201)
def render_preview(idea_id: UUID, storyboard_version_id: UUID = Query(...), db: Session = Depends(get_db)):
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    storyboard = db.get(StoryboardVersion, storyboard_version_id)
    if storyboard is None or storyboard.content_idea_id != idea_id:
        raise HTTPException(status_code=404, detail="Storyboard version not found for this idea")
    video_id = uuid4()
    try:
        storage_key, checksum, duration, width, height = render_silent_preview(
            storyboard.scenes, video_id, Path(get_settings().media_dir), get_settings().ffmpeg_binary, idea.format
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    video = RenderedVideo(id=video_id, content_idea_id=idea_id, storyboard_version_id=storyboard_version_id,
                          storage_key=storage_key, checksum=checksum, duration_seconds=duration,
                          width=width, height=height, status="PREVIEW_RENDERED", created_at=utc_now())
    db.add(video)
    db.commit()
    db.refresh(video)
    result = VideoRead.model_validate(video)
    result.preview_url = f"/api/v1/videos/{video.id}/file"
    return result


@router.get("/videos/{video_id}", response_model=VideoRead)
def get_video(video_id: UUID, db: Session = Depends(get_db)):
    video = db.get(RenderedVideo, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    result = VideoRead.model_validate(video)
    result.preview_url = f"/api/v1/videos/{video.id}/file"
    return result


@router.get("/videos/{video_id}/file")
def download_preview(video_id: UUID, db: Session = Depends(get_db)):
    video = db.get(RenderedVideo, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    root = Path(get_settings().media_dir).resolve()
    path = (root / video.storage_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="Preview file not found")
    return FileResponse(path, media_type="video/mp4", filename=f"aye-preview-{video.id}.mp4")


@router.get("/videos", response_model=list[VideoRead])
def list_videos(idea_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    query = select(RenderedVideo).order_by(RenderedVideo.created_at.desc()).limit(limit)
    if idea_id is not None:
        query = query.where(RenderedVideo.content_idea_id == idea_id)
    results = []
    for video in db.scalars(query).all():
        result = VideoRead.model_validate(video)
        result.preview_url = f"/api/v1/videos/{video.id}/file"
        results.append(result)
    return results
