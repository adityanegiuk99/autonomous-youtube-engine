import hashlib
import io
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import MediaAsset, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/media-assets", tags=["media"], dependencies=[Depends(require_api_token)])
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
IMAGE_TYPES = {"image/jpeg": ("jpg", "JPEG"), "image/png": ("png", "PNG"), "image/webp": ("webp", "WEBP")}
AUDIO_TYPES = {"audio/wav": "wav", "audio/x-wav": "wav", "audio/mpeg": "mp3", "audio/mp4": "m4a",
               "audio/aac": "aac", "audio/flac": "flac", "audio/ogg": "ogg"}
LICENSE_TYPES = ("owned", "licensed", "public_domain", "creative_commons")


class MediaAssetRead(BaseModel):
    id: UUID
    asset_type: str
    mime_type: str
    checksum: str
    license_type: str
    rights_confirmed: bool
    source_url: str | None
    original_filename: str
    duration_seconds: float | None
    created_at: datetime
    file_url: str = ""
    model_config = ConfigDict(from_attributes=True)


def _image_dimensions(content: bytes, expected_format: str) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != expected_format:
                raise ValueError("File content does not match the declared image type")
            if image.width * image.height > 50_000_000:
                raise ValueError("Image dimensions exceed the 50-megapixel limit")
            dimensions = (image.width, image.height)
            image.verify()
            return dimensions
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Uploaded image is invalid") from exc


def _audio_duration(path: Path) -> float:
    settings = get_settings()
    try:
        result = subprocess.run([settings.ffprobe_binary, "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                                 "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise ValueError("Audio could not be inspected; upload a supported audio file") from exc
    try:
        probe = json.loads(result.stdout)
        duration = float(probe["format"]["duration"])
        if not any(stream.get("codec_type") == "audio" for stream in probe.get("streams", [])):
            raise ValueError("Uploaded file contains no audio stream")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ValueError) and str(exc) == "Uploaded file contains no audio stream":
            raise
        raise ValueError("Audio duration is unavailable") from exc
    if not 0 < duration <= 900:
        raise ValueError("Audio duration must be between 0 and 900 seconds")
    return duration


def _to_read(asset: MediaAsset) -> MediaAssetRead:
    result = MediaAssetRead.model_validate(asset)
    result.file_url = f"/api/v1/media-assets/{asset.id}/file"
    return result


@router.get("", response_model=list[MediaAssetRead])
def list_assets(db: Session = Depends(get_db)):
    assets = db.scalars(select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(500)).all()
    return [_to_read(asset) for asset in assets]


@router.post("", response_model=MediaAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    license_type: Literal["owned", "licensed", "public_domain", "creative_commons"] = Form(...),
    rights_confirmed: bool = Form(...),
    source_url: str | None = Form(default=None, max_length=2048),
    db: Session = Depends(get_db),
):
    if not rights_confirmed:
        raise HTTPException(status_code=422, detail="Confirm that you have the right to use this asset")
    if license_type != "owned" and not source_url:
        raise HTTPException(status_code=422, detail="Provide the source URL for non-owned media")
    parsed_source = urlparse(source_url) if source_url else None
    if parsed_source and (parsed_source.scheme != "https" or not parsed_source.hostname or parsed_source.username or parsed_source.password):
        raise HTTPException(status_code=422, detail="Source URL must be HTTPS and cannot contain credentials")
    mime_type = (file.content_type or "").lower()
    if mime_type not in IMAGE_TYPES and mime_type not in AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Upload JPEG, PNG, WEBP, WAV, MP3, M4A, AAC, FLAC, or OGG media")
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Media files are limited to 30 MB")
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    asset_id = uuid4()
    asset_type = "image" if mime_type in IMAGE_TYPES else "audio"
    extension = IMAGE_TYPES[mime_type][0] if asset_type == "image" else AUDIO_TYPES[mime_type]
    media_dir = Path(get_settings().media_dir).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"asset-{asset_id}.{extension}"
    path = media_dir / storage_key
    path.write_bytes(content)
    duration = None
    try:
        if asset_type == "image":
            _image_dimensions(bytes(content), IMAGE_TYPES[mime_type][1])
        else:
            duration = _audio_duration(path)
    except ValueError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    original_filename = (file.filename or "upload").replace("\\", "/").split("/")[-1]
    original_filename = re.sub(r"[\x00-\x1f\x7f]", "", original_filename)[:255] or "upload"
    asset = MediaAsset(id=asset_id, storage_key=storage_key, asset_type=asset_type, mime_type=mime_type,
                       checksum=hashlib.sha256(content).hexdigest(), license_type=license_type,
                       rights_confirmed=True, source_url=source_url, original_filename=original_filename,
                       duration_seconds=duration, created_at=utc_now())
    db.add(asset)
    try:
        db.commit()
        db.refresh(asset)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return _to_read(asset)


@router.get("/{asset_id}/file")
def download_asset(asset_id: UUID, db: Session = Depends(get_db)):
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    root = Path(get_settings().media_dir).resolve()
    path = (root / asset.storage_key).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_filename)
