import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.content_hashing import production_content_hash
from app.models import ContentIdea, MediaAsset, ProductionAttempt, RenderedVideo, ScriptVersion, StoryboardVersion, utc_now
from app.production.render import render_production
from app.workflows import record_workflow_event


@dataclass
class ProductionContext:
    idea: ContentIdea
    storyboard: StoryboardVersion
    script: ScriptVersion
    assets: dict[UUID, MediaAsset]
    media_root: Path
    settings: Settings


def load_production_context(db: Session, idea_id: UUID, storyboard_version_id: UUID) -> ProductionContext:
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    storyboard = db.get(StoryboardVersion, storyboard_version_id)
    if storyboard is None or storyboard.content_idea_id != idea_id:
        raise HTTPException(status_code=404, detail="Storyboard version not found for this idea")

    used_ids = {UUID(str(scene[field])) for scene in storyboard.scenes
                for field in ("image_asset_id", "audio_asset_id") if scene.get(field)}
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

    script = db.get(ScriptVersion, storyboard.script_version_id)
    if script is None:
        raise HTTPException(status_code=409, detail="Storyboard script version is missing")
    settings = get_settings()
    return ProductionContext(idea, storyboard, script, assets, Path(settings.media_dir).resolve(), settings)


def media_manifest(assets: dict[UUID, MediaAsset]) -> list[dict]:
    return [{"asset_id": str(asset.id), "asset_type": asset.asset_type,
             "license_type": asset.license_type, "source_url": asset.source_url,
             "checksum": asset.checksum, "rights_confirmed": asset.rights_confirmed}
            for asset in assets.values()]


def production_lock(db: Session, idea_id: UUID, storyboard_version_id: UUID) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        digest = hashlib.sha256(f"aye:production:{idea_id}:{storyboard_version_id}".encode("ascii")).digest()
        keys = (int.from_bytes(digest[:4], "big", signed=True), int.from_bytes(digest[4:8], "big", signed=True))
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(:key1, :key2)"), {"key1": keys[0], "key2": keys[1]})


def _source_bytes(media_root: Path, assets: dict[UUID, MediaAsset]) -> int:
    total = 0
    for asset in assets.values():
        path = (media_root / asset.storage_key).resolve()
        if path.parent != media_root or not path.is_file():
            raise ValueError("A referenced media file is missing or outside media storage")
        total += path.stat().st_size
    return total


def _cleanup_attempt(media_root: Path, attempt_id: UUID) -> bool:
    cleaned = True
    for key in (f"{attempt_id}.mp4", f"{attempt_id}-thumb.jpg", f"{attempt_id}-captions.vtt"):
        path = media_root / key
        if path.parent.resolve() != media_root:
            cleaned = False
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            cleaned = False
    return cleaned


def fail_attempt(db: Session, attempt: ProductionAttempt, idea: ContentIdea,
                 failure_class: str, cleanup_succeeded: bool,
                 render_duration_seconds: float | None = None, source_bytes: int | None = None) -> None:
    previous_state = idea.status
    idea.status = "PRODUCTION_FAILED"
    attempt.status = "failed"
    attempt.finished_at = utc_now()
    attempt.render_duration_seconds = render_duration_seconds
    attempt.source_bytes = source_bytes
    attempt.failure_class = failure_class
    record_workflow_event(db, idea.id, idea.status, "production_failed",
                          "Production render failed; review source assets and rendering configuration before retrying",
                          {"failure_class": failure_class,
                           "storyboard_version_id": str(attempt.storyboard_version_id),
                           "attempt_id": str(attempt.id), "attempt_number": attempt.attempt_number,
                           "render_duration_seconds": render_duration_seconds, "source_bytes": source_bytes,
                           "partial_output_cleanup_succeeded": cleanup_succeeded},
                          previous_state=previous_state, actor="system")


def execute_production_attempt(db: Session, attempt: ProductionAttempt,
                               context: ProductionContext) -> tuple[RenderedVideo | None, str | None]:
    started = time.perf_counter()
    source_bytes = None
    try:
        source_bytes = _source_bytes(context.media_root, context.assets)
        result = render_production(context.storyboard.scenes, context.assets, attempt.id,
                                   context.media_root, context.settings.ffmpeg_binary,
                                   context.settings.ffprobe_binary, context.idea.format)
        output_path = (context.media_root / result["storage_key"]).resolve()
        if output_path.parent != context.media_root or not output_path.is_file():
            raise ValueError("Rendered output is missing or outside media storage")
        output_bytes = output_path.stat().st_size
    except (RuntimeError, ValueError, OSError) as exc:
        duration = round(time.perf_counter() - started, 3)
        cleanup_succeeded = _cleanup_attempt(context.media_root, attempt.id)
        fail_attempt(db, attempt, context.idea,
                     "input_validation" if isinstance(exc, ValueError) else "render_tool_or_storage",
                     cleanup_succeeded, duration, source_bytes)
        db.commit()
        return None, str(exc)

    duration = round(time.perf_counter() - started, 3)
    content_hash = production_content_hash(context.idea, context.script, context.storyboard,
                                           result["media_manifest"], result["checksum"])
    video = RenderedVideo(
        id=attempt.id, content_idea_id=context.idea.id,
        storyboard_version_id=context.storyboard.id,
        storage_key=result["storage_key"], checksum=result["checksum"], content_hash=content_hash,
        duration_seconds=result["duration_seconds"], width=result["width"], height=result["height"],
        status=result["qa_report"]["status"], video_type="production",
        thumbnail_key=result["thumbnail_key"], captions_key=result["captions_key"],
        captions_checksum=result["captions_checksum"], media_manifest=result["media_manifest"],
        qa_report=result["qa_report"], created_at=utc_now())
    attempt.status = "completed"
    attempt.finished_at = utc_now()
    attempt.render_duration_seconds = duration
    attempt.source_bytes = source_bytes
    attempt.output_bytes = output_bytes
    attempt.video_id = video.id
    db.add(video)
    previous_state = context.idea.status
    context.idea.status = video.status
    record_workflow_event(db, context.idea.id, context.idea.status, "production_rendered",
                          "Production render completed with technical QA",
                          {"video_id": str(video.id), "content_hash": content_hash,
                           "technical_qa_status": video.qa_report.get("status"),
                           "storyboard_version_id": str(context.storyboard.id),
                           "attempt_id": str(attempt.id), "attempt_number": attempt.attempt_number,
                           "render_duration_seconds": duration,
                           "source_bytes": source_bytes, "output_bytes": output_bytes},
                          previous_state=previous_state)
    try:
        db.commit()
        db.refresh(video)
    except Exception:
        db.rollback()
        _cleanup_attempt(context.media_root, attempt.id)
        raise
    return video, None
