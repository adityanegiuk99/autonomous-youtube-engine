import hashlib
import time
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.content_hashing import production_content_hash
from app.database import get_db
from app.models import Approval, ContentIdea, MediaAsset, ProductionAttempt, RenderedVideo, ScriptVersion, StoryboardVersion, WorkflowEvent, utc_now
from app.production.preview import render_silent_preview
from app.production.render import render_production
from app.security import require_api_token
from app.workflows import record_workflow_event

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


def _video_read(video: RenderedVideo) -> VideoRead:
    result = VideoRead.model_validate(video)
    result.preview_url = f"/api/v1/videos/{video.id}/file"
    result.thumbnail_url = f"/api/v1/videos/{video.id}/thumbnail" if video.thumbnail_key else None
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_matches(path: Path, root: Path, checksum: str) -> bool:
    if path.parent != root or not path.is_file():
        return False
    try:
        return _sha256_file(path) == checksum
    except OSError:
        return False


def _media_manifest(assets: dict[UUID, MediaAsset]) -> list[dict]:
    return [{"asset_id": str(asset.id), "asset_type": asset.asset_type,
             "license_type": asset.license_type, "source_url": asset.source_url,
             "checksum": asset.checksum, "rights_confirmed": asset.rights_confirmed}
            for asset in assets.values()]


def _source_media_bytes(media_root: Path, assets: dict[UUID, MediaAsset]) -> int:
    sizes = []
    for asset in assets.values():
        path = (media_root / asset.storage_key).resolve()
        if path.parent != media_root or not path.is_file():
            raise ValueError("A referenced media file is missing or outside media storage")
        sizes.append(path.stat().st_size)
    return sum(sizes)


def _remove_generated_files(media_root: Path, *storage_keys: str) -> bool:
    cleaned = True
    for storage_key in storage_keys:
        path = media_root / storage_key
        if path.parent.resolve() != media_root:
            cleaned = False
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            cleaned = False
    return cleaned


@router.post("/ideas/{idea_id}/render-preview", response_model=VideoRead, status_code=201)
def render_preview(idea_id: UUID, storyboard_version_id: UUID = Query(...), db: Session = Depends(get_db)):
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    storyboard = db.get(StoryboardVersion, storyboard_version_id)
    if storyboard is None or storyboard.content_idea_id != idea_id:
        raise HTTPException(status_code=404, detail="Storyboard version not found for this idea")
    video_id = uuid4()
    settings = get_settings()
    media_dir = Path(settings.media_dir).resolve()
    try:
        storage_key, checksum, duration, width, height = render_silent_preview(
            storyboard.scenes, video_id, media_dir, settings.ffmpeg_binary, idea.format
        )
    except (RuntimeError, ValueError, OSError) as exc:
        cleanup_succeeded = _remove_generated_files(media_dir, f"{video_id}.mp4")
        record_workflow_event(db, idea.id, idea.status, "preview_failed",
                              "Silent preview failed; review storyboard content and FFmpeg configuration",
                              {"failure_class": "input_validation" if isinstance(exc, ValueError) else "render_tool_or_storage",
                               "partial_output_cleanup_succeeded": cleanup_succeeded},
                              previous_state=idea.status, actor="system")
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    video = RenderedVideo(id=video_id, content_idea_id=idea_id, storyboard_version_id=storyboard_version_id,
                          storage_key=storage_key, checksum=checksum, duration_seconds=duration,
                          width=width, height=height, status="PREVIEW_RENDERED", created_at=utc_now())
    db.add(video)
    record_workflow_event(db, idea.id, idea.status, "preview_rendered", "Silent animatic preview rendered",
                          {"video_id": str(video_id), "checksum": checksum}, previous_state=idea.status)
    db.commit()
    db.refresh(video)
    result = VideoRead.model_validate(video)
    result.preview_url = f"/api/v1/videos/{video.id}/file"
    result.thumbnail_url = f"/api/v1/videos/{video.id}/thumbnail" if video.thumbnail_key else None
    return result


@router.post("/ideas/{idea_id}/render-production", response_model=VideoRead, status_code=201,
             responses={200: {"model": VideoRead, "description": "Idempotent replay of an intact QA-passed render"},
                        409: {"description": "The exact content already has a human decision"}})
def render_final_video(idea_id: UUID, response: Response, storyboard_version_id: UUID = Query(...), db: Session = Depends(get_db)):
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

    # Keep concurrent requests for the same immutable render inputs from both
    # starting FFmpeg. The transaction lock is released on commit, error, or disconnect.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        lock_digest = hashlib.sha256(
            f"aye:production:{idea_id}:{storyboard_version_id}".encode("ascii")
        ).digest()
        lock_keys = (int.from_bytes(lock_digest[:4], "big", signed=True),
                     int.from_bytes(lock_digest[4:8], "big", signed=True))
        db.execute(text("SELECT pg_advisory_xact_lock(:key1, :key2)"),
                   {"key1": lock_keys[0], "key2": lock_keys[1]})

    settings = get_settings()
    media_dir = Path(settings.media_dir).resolve()
    script = db.get(ScriptVersion, storyboard.script_version_id)
    if script is None:
        raise HTTPException(status_code=409, detail="Storyboard script version is missing")

    manifest = _media_manifest(assets)
    previous_renders = db.scalars(select(RenderedVideo).where(
        RenderedVideo.content_idea_id == idea_id,
        RenderedVideo.storyboard_version_id == storyboard_version_id,
        RenderedVideo.video_type == "production",
    ).order_by(desc(RenderedVideo.created_at))).all()
    for previous in previous_renders:
        if previous.qa_report is None or previous.qa_report.get("status") != "TECHNICAL_QA_PASSED" or not previous.content_hash:
            continue
        same_content = production_content_hash(idea, script, storyboard, manifest, previous.checksum)
        if same_content != previous.content_hash:
            continue
        prior_decision = db.scalar(select(Approval.id).where(Approval.video_id == previous.id).limit(1))
        if prior_decision is not None:
            raise HTTPException(status_code=409,
                                detail="This exact storyboard and media version already has a human decision. Revise the content before rendering another review version.")
        video_path = (media_dir / previous.storage_key).resolve()
        thumbnail_path = (media_dir / previous.thumbnail_key).resolve() if previous.thumbnail_key else None
        sources_intact = all(
            _file_matches((media_dir / asset.storage_key).resolve(), media_dir, asset.checksum)
            for asset in assets.values()
        )
        if (sources_intact and _file_matches(video_path, media_dir, previous.checksum)
                and thumbnail_path is not None and thumbnail_path.parent == media_dir and thumbnail_path.is_file()):
            response.status_code = 200
            return _video_read(previous)

    running_attempt = db.scalar(select(ProductionAttempt).where(
        ProductionAttempt.content_idea_id == idea_id,
        ProductionAttempt.storyboard_version_id == storyboard_version_id,
        ProductionAttempt.status == "running",
    ))
    if running_attempt is not None:
        attempt_started_at = running_attempt.started_at
        if attempt_started_at.tzinfo is None:
            attempt_started_at = attempt_started_at.replace(tzinfo=utc_now().tzinfo)
        age_seconds = max(0, int((utc_now() - attempt_started_at).total_seconds()))
        raise HTTPException(status_code=409,
                            detail=f"Production attempt {running_attempt.id} is still recorded as running ({age_seconds}s old). Inspect and recover a stale attempt in Operations before retrying.")

    attempt_events = db.scalars(select(WorkflowEvent).where(
        WorkflowEvent.content_idea_id == idea_id,
        WorkflowEvent.event_type.in_(("production_failed", "production_rendered")),
    )).all()
    legacy_attempt_count = sum(
        1 for event in attempt_events
        if (event.metadata_json or {}).get("storyboard_version_id") == str(storyboard_version_id)
    )
    attempt_rows = db.scalars(select(ProductionAttempt).where(
        ProductionAttempt.content_idea_id == idea_id,
        ProductionAttempt.storyboard_version_id == storyboard_version_id,
    )).all()
    recorded_attempts = max(legacy_attempt_count, len(attempt_rows))
    if recorded_attempts >= settings.max_production_attempts:
        raise HTTPException(status_code=409,
                            detail=f"This storyboard reached the {settings.max_production_attempts}-attempt render limit. Revise the storyboard or its media inputs before trying again.")
    attempt_number = recorded_attempts + 1

    video_id = uuid4()
    attempt = ProductionAttempt(id=video_id, content_idea_id=idea_id,
                                storyboard_version_id=storyboard_version_id,
                                attempt_number=attempt_number, status="running", started_at=utc_now())
    db.add(attempt)
    db.commit()
    render_started = time.perf_counter()
    source_bytes: int | None = None
    try:
        source_bytes = _source_media_bytes(media_dir, assets)
        result = render_production(storyboard.scenes, assets, video_id, media_dir,
                                   settings.ffmpeg_binary, settings.ffprobe_binary, idea.format)
        output_path = (media_dir / result["storage_key"]).resolve()
        if output_path.parent != media_dir or not output_path.is_file():
            raise ValueError("Rendered output is missing or outside media storage")
        output_bytes = output_path.stat().st_size
    except (RuntimeError, ValueError, OSError) as exc:
        render_duration_seconds = round(time.perf_counter() - render_started, 3)
        cleanup_succeeded = _remove_generated_files(media_dir, f"{video_id}.mp4", f"{video_id}-thumb.jpg")
        attempt.status = "failed"
        attempt.finished_at = utc_now()
        attempt.render_duration_seconds = render_duration_seconds
        attempt.source_bytes = source_bytes
        attempt.failure_class = "input_validation" if isinstance(exc, ValueError) else "render_tool_or_storage"
        previous_state = idea.status
        idea.status = "PRODUCTION_FAILED"
        record_workflow_event(db, idea.id, idea.status, "production_failed",
                              "Production render failed; correct the source assets or rendering configuration before retrying",
                              {"failure_class": "input_validation" if isinstance(exc, ValueError) else "render_tool_or_storage",
                               "storyboard_version_id": str(storyboard_version_id),
                               "attempt_id": str(attempt.id),
                               "attempt_number": attempt_number,
                               "render_duration_seconds": render_duration_seconds,
                               "source_bytes": source_bytes,
                               "partial_output_cleanup_succeeded": cleanup_succeeded},
                              previous_state=previous_state, actor="system")
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    render_duration_seconds = round(time.perf_counter() - render_started, 3)
    content_hash = production_content_hash(idea, script, storyboard, result["media_manifest"], result["checksum"])
    video = RenderedVideo(id=video_id, content_idea_id=idea_id, storyboard_version_id=storyboard_version_id,
                          storage_key=result["storage_key"], checksum=result["checksum"],
                          content_hash=content_hash,
                          duration_seconds=result["duration_seconds"], width=result["width"], height=result["height"],
                          status=result["qa_report"]["status"], video_type="production",
                          thumbnail_key=result["thumbnail_key"], media_manifest=result["media_manifest"],
                          qa_report=result["qa_report"], created_at=utc_now())
    attempt.status = "completed"
    attempt.finished_at = utc_now()
    attempt.render_duration_seconds = render_duration_seconds
    attempt.source_bytes = source_bytes
    attempt.output_bytes = output_bytes
    attempt.video_id = video_id
    db.add(video)
    previous_state = idea.status
    idea.status = video.status
    record_workflow_event(db, idea.id, idea.status, "production_rendered",
                          "Production render completed with technical QA",
                          {"video_id": str(video.id), "content_hash": content_hash,
                           "technical_qa_status": video.qa_report.get("status"),
                           "storyboard_version_id": str(storyboard_version_id),
                           "attempt_id": str(attempt.id),
                           "attempt_number": attempt_number,
                           "render_duration_seconds": render_duration_seconds,
                           "source_bytes": source_bytes,
                           "output_bytes": output_bytes},
                          previous_state=previous_state)
    try:
        db.commit()
        db.refresh(video)
    except Exception:
        db.rollback()
        (media_dir / result["storage_key"]).unlink(missing_ok=True)
        (media_dir / result["thumbnail_key"]).unlink(missing_ok=True)
        raise
    return _video_read(video)


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
