import hashlib
import json


def production_content_hash(idea, script, storyboard, media_manifest: list[dict], video_checksum: str) -> str:
    identity = {
        "idea_id": str(idea.id),
        "idea_title": idea.title,
        "format": idea.format,
        "script_version": script.version,
        "script_hash": script.content_hash,
        "storyboard_version": storyboard.version,
        "storyboard_hash": storyboard.content_hash,
        "media": sorted(media_manifest, key=lambda item: item["asset_id"]),
        "video_checksum": video_checksum,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
