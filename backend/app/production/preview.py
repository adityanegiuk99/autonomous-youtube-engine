import hashlib
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def _make_scene_image(scene: dict, index: int, total: int, width: int, height: int, destination: Path) -> None:
    image = Image.new("RGB", (width, height), (22, 43, 35))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 10), fill=(97, 169, 125))
    margin = int(width * 0.085)
    title_font = _font(max(20, int(width * 0.055)))
    text_font = _font(max(16, int(width * 0.034)))
    draw.text((margin, int(height * 0.12)), f"SCENE {index + 1:02d} / {total:02d}", font=_font(max(12, width // 48)), fill=(142, 194, 158))

    title = scene.get("visual_description", "").strip()
    y = int(height * 0.25)
    for line in _wrap(title, title_font, draw, width - margin * 2)[:5]:
        draw.text((margin, y), line, font=title_font, fill=(244, 248, 244))
        y += int(title_font.size * 1.35)

    subtitle = scene.get("subtitle", "").strip() or scene.get("voiceover", "").strip()
    subtitle_lines = _wrap(subtitle, text_font, draw, width - margin * 2)
    block_height = min(len(subtitle_lines), 7) * int(text_font.size * 1.45) + 32
    top = height - int(height * 0.17) - block_height
    draw.rounded_rectangle((margin, top, width - margin, top + block_height), radius=16, fill=(12, 25, 20))
    y = top + 16
    for line in subtitle_lines[:7]:
        draw.text((margin + 18, y), line, font=text_font, fill=(231, 238, 232))
        y += int(text_font.size * 1.45)
    image.save(destination, format="PNG", optimize=True)


def render_silent_preview(scenes: list[dict], video_id: UUID, media_dir: Path, ffmpeg_binary: str,
                          aspect: str, timeout_seconds: int = 240) -> tuple[str, str, float, int, int]:
    width, height = (720, 1280) if aspect == "short" else (1280, 720)
    total_duration = sum(float(scene["duration_seconds"]) for scene in scenes)
    if total_duration <= 0 or total_duration > 900:
        raise ValueError("Storyboard duration must be between 0 and 900 seconds")
    media_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{video_id}.mp4"
    final_path = (media_dir / storage_key).resolve()
    with tempfile.TemporaryDirectory(prefix="aye-preview-") as temp_name:
        temp_dir = Path(temp_name)
        concat_path = temp_dir / "concat.txt"
        rows = []
        for index, scene in enumerate(scenes):
            frame_path = temp_dir / f"frame-{index:04d}.png"
            _make_scene_image(scene, index, len(scenes), width, height, frame_path)
            rows.extend([f"file 'frame-{index:04d}.png'", f"duration {float(scene['duration_seconds']):.3f}"])
        last_frame = f"frame-{len(scenes)-1:04d}.png"
        rows.append(f"file '{last_frame}'")
        concat_path.write_text("\n".join(rows), encoding="utf-8")
        command = [ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                   "-i", str(concat_path), "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                   "-movflags", "+faststart", str(final_path)]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout_seconds, cwd=temp_dir)
        except FileNotFoundError as exc:
            raise RuntimeError("FFmpeg executable was not found; configure AYE_FFMPEG_BINARY") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Preview render exceeded the time limit") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"FFmpeg preview render failed: {exc.stderr[-1000:]}") from exc
    digest = hashlib.sha256()
    with final_path.open("rb") as rendered:
        for chunk in iter(lambda: rendered.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    return storage_key, checksum, total_duration, width, height
