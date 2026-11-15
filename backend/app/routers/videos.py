from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.content_hashing import production_content_hash
from app.database import get_db
from app.models import ContentIdea, MediaAsset, RenderedVideo, ScriptVersion, StoryboardVersion, utc_now
from app.production.preview import render_silent_preview
from app.production.render import render_production
from app.security import require_api_token

router = APIRouter(tags=["videos"], dependencies=[Depends(require_api_token)])


class VideoRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    storyboard_version_id: UUID
    checksum: str
    content_hash: str | None = None
    duration_seconds: float
    width: int
    height: int
    status: str
    created_at: datetime
    preview_url: str = ""
    thumbnail_url: str | None = None
    video_type: str = "animatic"
    qa_report: dict | None = None
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
    result.thumbnail_url = f"/api/v1/videos/{video.id}/thumbnail" if video.thumbnail_key else None
    return result


@router.post("/ideas/{idea_id}/render-production", response_model=VideoRead, status_code=201)
def render_final_video(idea_id: UUID, storyboard_version_id: UUID = Query(...), db: Session = Depends(get_db)):
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    storyboard = db.get(StoryboardVersion, storyboard_version_id)
    if storyboard is None or storyboard.content_idea_id != idea_id:
        raise HTTPException(status_code=404, detail="Storyboard version not found for this idea")

    used_ids = {UUID(str(scene[field])) for scene in storyboard.scenes for field in ("image_asset_id", "audio_asset_id") if scene.get(field)}
    if not used_ids or any(not scene.get("image_asset_id") or not scene.get("audio_asset_id") for scene in storyboard.scenes):
        raise HTTPException(status_code=422, detail="Every production scene needs an uploaded image and voice audio asset")
    assets = {asset.id: asset for asset in db.scalars(select(MediaAsset).where(MediaAsset.id.in_(used_ids))).all()}
    if len(assets) != len(used_ids):
        raise HTTPException(status_code=422, detail="A storyboard media asset is missing")
    for scene in storyboard.scenes:
        image = assets[UUID(str(scene["image_asset_id"]))]
        audio = assets[UUID(str(scene["audio_asset_id"]))]
        if image.asset_type != "image" or audio.asset_type != "audio" or not image.rights_confirmed or not audio.rights_confirmed:
            raise HTTPException(status_code=422, detail="Storyboard asset types or rights confirmation are invalid")
        if any(asset.license_type != "owned" for asset in (image, audio)) and not scene.get("source_attribution"):
            raise HTTPException(status_code=422, detail="Non-owned storyboard media needs source attribution")

    settings = get_settings()
    video_id = uuid4()
    media_dir = Path(settings.media_dir).resolve()
    try:
        result = render_production(storyboard.scenes, assets, video_id, media_dir,
                                   settings.ffmpeg_binary, settings.ffprobe_binary, idea.format)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    script = db.get(ScriptVersion, storyboard.script_version_id)
    if script is None:
        raise HTTPException(status_code=409, detail="Storyboard script version is missing")
    content_hash = production_content_hash(idea, script, storyboard, result["media_manifest"], result["checksum"])
    video = RenderedVideo(id=video_id, content_idea_id=idea_id, storyboard_version_id=storyboard_version_id,
                          storage_key=result["storage_key"], checksum=result["checksum"],
                          content_hash=content_hash,
                          duration_seconds=result["duration_seconds"], width=result["width"], height=result["height"],
                          status=result["qa_report"]["status"], video_type="production",
                          thumbnail_key=result["thumbnail_key"], media_manifest=result["media_manifest"],
                          qa_report=result["qa_report"], created_at=utc_now())
    db.add(video)
    idea.status = video.status
    try:
        db.commit()
        db.refresh(video)
    except Exception:
        db.rollback()
        (media_dir / result["storage_key"]).unlink(missing_ok=True)
        (media_dir / result["thumbnail_key"]).unlink(missing_ok=True)
        raise
    response = VideoRead.model_validate(video)
    response.preview_url = f"/api/v1/videos/{video.id}/file"
    response.thumbnail_url = f"/api/v1/videos/{video.id}/thumbnail"
    return response


@router.get("/videos/{video_id}", response_model=VideoRead)
def get_video(video_id: UUID, db: Session = Depends(get_db)):
    video = db.get(RenderedVideo, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    result = VideoRead.model_validate(video)
    result.preview_url = f"/api/v1/videos/{video.id}/file"
    result.thumbnail_url = f"/api/v1/videos/{video.id}/thumbnail" if video.thumbnail_key else None
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
    return FileResponse(path, media_type="video/mp4", filename=f"aye-{video.video_type}-{video.id}.mp4")


@router.get("/videos/{video_id}/thumbnail")
def download_thumbnail(video_id: UUID, db: Session = Depends(get_db)):
    video = db.get(RenderedVideo, video_id)
    if video is None or not video.thumbnail_key:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    root = Path(get_settings().media_dir).resolve()
    path = (root / video.thumbnail_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")
    return FileResponse(path, media_type="image/jpeg", filename=f"aye-thumbnail-{video.id}.jpg")


@router.get("/videos", response_model=list[VideoRead])
def list_videos(idea_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    query = select(RenderedVideo).order_by(RenderedVideo.created_at.desc()).limit(limit)
    if idea_id is not None:
        query = query.where(RenderedVideo.content_idea_id == idea_id)
    results = []
    for video in db.scalars(query).all():
        result = VideoRead.model_validate(video)
        result.preview_url = f"/api/v1/videos/{video.id}/file"
        result.thumbnail_url = f"/api/v1/videos/{video.id}/thumbnail" if video.thumbnail_key else None
        results.append(result)
    return results
