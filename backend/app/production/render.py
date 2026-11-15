import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _lines(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _prepare_frame(scene: dict, image_path: Path, destination: Path, width: int, height: int) -> None:
    with Image.open(image_path) as source:
        image = ImageOps.fit(source.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
    image = ImageEnhance.Brightness(image).enhance(0.60)
    draw = ImageDraw.Draw(image, "RGBA")
    padding = int(width * 0.07)
    title_font = _font(max(20, width // 22))
    subtitle_font = _font(max(16, width // 32))
    title_lines = _lines(scene.get("visual_description", ""), title_font, draw, width - 2 * padding)[:4]
    y = int(height * 0.12)
    for line in title_lines:
        draw.text((padding, y), line, font=title_font, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 180))
        y += int(title_font.size * 1.3)

    subtitle = (scene.get("subtitle") or scene.get("voiceover") or "").strip()
    subtitle_lines = _lines(subtitle, subtitle_font, draw, width - 2 * padding)[:5]
    line_height = int(subtitle_font.size * 1.45)
    box_height = len(subtitle_lines) * line_height + 28
    box_top = height - padding - box_height - int(height * 0.08)
    draw.rounded_rectangle((padding, box_top, width - padding, box_top + box_height), radius=18, fill=(7, 17, 13, 210))
    y = box_top + 14
    for line in subtitle_lines:
        draw.text((padding + 14, y), line, font=subtitle_font, fill=(255, 255, 255, 255))
        y += line_height
    credits = "  ·  ".join(scene.get("source_attribution", []))
    if credits:
        credit_font = _font(max(10, width // 90))
        draw.text((padding, height - max(12, width // 80)), credits[:240], font=credit_font, fill=(255, 255, 255, 210))
    image.convert("RGB").save(destination, format="PNG", optimize=True)


def _run(command: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg/FFprobe executable was not found; check its configuration") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Media processing exceeded its time limit") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Media processing failed: {exc.stderr[-1200:]}") from exc


def render_production(scenes: list[dict], assets: dict[UUID, object], video_id: UUID, media_dir: Path,
                      ffmpeg: str, ffprobe: str, aspect: str) -> dict:
    if not scenes or len(scenes) > 50:
        raise ValueError("Production renders support 1–50 storyboard scenes")
    total_duration = sum(float(scene["duration_seconds"]) for scene in scenes)
    if not 0 < total_duration <= 900:
        raise ValueError("Production duration must be between 0 and 900 seconds")
    width, height = (720, 1280) if aspect == "short" else (1280, 720)
    media_dir.mkdir(parents=True, exist_ok=True)
    video_key = f"{video_id}.mp4"
    thumb_key = f"{video_id}-thumb.jpg"
    final_path = (media_dir / video_key).resolve()
    thumbnail_path = (media_dir / thumb_key).resolve()
    manifest = []

    for asset in assets.values():
        asset_path = (media_dir / asset.storage_key).resolve()
        if asset_path.parent != media_dir.resolve() or not asset_path.is_file():
            raise ValueError("A referenced media file is missing")
        digest = hashlib.sha256()
        with asset_path.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != asset.checksum:
            raise ValueError("A media asset changed after upload")

    with tempfile.TemporaryDirectory(prefix="aye-production-") as temp_name:
        temp_dir = Path(temp_name)
        concat_file = temp_dir / "segments.txt"
        rows: list[str] = []
        for index, scene in enumerate(scenes):
            image_asset = assets[UUID(str(scene["image_asset_id"]))]
            audio_asset = assets[UUID(str(scene["audio_asset_id"]))]
            image_path = media_dir / image_asset.storage_key
            audio_path = media_dir / audio_asset.storage_key
            if not image_path.is_file() or not audio_path.is_file():
                raise ValueError("A referenced media file is missing")
            duration = float(scene["duration_seconds"])
            audio_duration = float(audio_asset.duration_seconds or 0)
            if duration + 0.25 < audio_duration:
                raise ValueError(f"Scene {index + 1} is shorter than its voice audio")

            frame = temp_dir / f"frame-{index:04d}.png"
            _prepare_frame(scene, image_path, frame, width, height)
            segment = temp_dir / f"segment-{index:04d}.mp4"
            _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "30",
                  "-i", str(frame), "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
                  "-vf", "format=yuv420p", "-af", "apad", "-t", f"{duration:.3f}", "-r", "30",
                  "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-c:a", "aac",
                  "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(segment)], temp_dir)
            rows.append(f"file 'segment-{index:04d}.mp4'")
            for asset in (image_asset, audio_asset):
                manifest.append({"asset_id": str(asset.id), "asset_type": asset.asset_type,
                                 "license_type": asset.license_type, "source_url": asset.source_url,
                                 "checksum": asset.checksum, "rights_confirmed": asset.rights_confirmed})
            if index == 0:
                with Image.open(frame) as thumb:
                    thumb.convert("RGB").save(thumbnail_path, format="JPEG", quality=88, optimize=True)

        concat_file.write_text("\n".join(rows), encoding="utf-8")
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i",
              str(concat_file), "-c", "copy", "-movflags", "+faststart", str(final_path)], temp_dir, timeout=300)

    probe = _run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(final_path)],
                 media_dir)
    try:
        inspected = json.loads(probe.stdout)
        streams = inspected["streams"]
        video_stream = next(stream for stream in streams if stream.get("codec_type") == "video")
        audio_stream = next(stream for stream in streams if stream.get("codec_type") == "audio")
        actual_duration = float(inspected["format"]["duration"])
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        final_path.unlink(missing_ok=True)
        thumbnail_path.unlink(missing_ok=True)
        raise RuntimeError("Rendered media failed technical inspection") from exc

    manifest = list({item["asset_id"]: item for item in manifest}.values())
    checks = {
        "container_mp4": final_path.suffix.lower() == ".mp4",
        "video_codec_h264": video_stream.get("codec_name") == "h264",
        "audio_codec_aac": audio_stream.get("codec_name") == "aac",
        "expected_resolution": (int(video_stream.get("width", 0)), int(video_stream.get("height", 0))) == (width, height),
        "duration_matches_storyboard": abs(actual_duration - total_duration) <= max(1.5, total_duration * 0.03),
        "all_assets_rights_confirmed": all(item["rights_confirmed"] for item in manifest),
    }
    qa_report = {"status": "TECHNICAL_QA_PASSED" if all(checks.values()) else "TECHNICAL_QA_FAILED",
                 "checks": checks, "duration_seconds": actual_duration,
                 "note": "Technical file and supplied asset metadata checks only; editorial accuracy and license terms are not independently verified."}
    digest = hashlib.sha256()
    with final_path.open("rb") as rendered:
        for chunk in iter(lambda: rendered.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"storage_key": video_key, "thumbnail_key": thumb_key, "checksum": digest.hexdigest(),
            "duration_seconds": actual_duration, "width": width, "height": height,
            "media_manifest": manifest, "qa_report": qa_report}
