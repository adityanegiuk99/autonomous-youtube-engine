import csv
import io
import math
import re
import statistics
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AnalyticsSnapshot, Channel, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_api_token)])
MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
REQUIRED_COLUMNS = {"video_id", "collected_at", "views", "impressions", "click_through_rate_percent",
                    "watch_time_minutes", "average_view_duration_seconds", "likes", "comments", "subscribers_gained"}


@router.get("/csv-template", response_class=Response)
def csv_template():
    columns = "video_id,collected_at,views,impressions,click_through_rate_percent,watch_time_minutes,average_view_duration_seconds,likes,comments,subscribers_gained\n"
    return Response(content=columns, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=aye-analytics-template.csv"})


class ImportResult(BaseModel):
    import_id: UUID
    channel_id: UUID
    rows_imported: int
    rows_updated: int
    rows_total: int
    source: str = "user_csv"


class TopVideo(BaseModel):
    video_id: str
    views: int
    average_view_duration_seconds: float


class AnalyticsSummary(BaseModel):
    channel_id: UUID
    video_count: int
    sample_size: str
    data_window_start: datetime | None
    latest_snapshot_at: datetime | None
    views_total: int
    impressions_total: int
    weighted_ctr_percent: float | None
    watch_time_minutes_total: float
    average_view_duration_seconds: float | None
    top_videos: list[TopVideo]
    interpretation: str


def _parse_row(row: dict[str, str], line_number: int) -> tuple[str, datetime, dict]:
    try:
        video_id = (row.get("video_id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError("video_id must be an 11-character YouTube video ID")
        collected = datetime.fromisoformat((row.get("collected_at") or "").strip().replace("Z", "+00:00"))
        if collected.tzinfo is None:
            collected = collected.replace(tzinfo=timezone.utc)
        collected = collected.astimezone(timezone.utc)
        if collected > utc_now().replace(hour=23, minute=59, second=59, microsecond=0):
            raise ValueError("collected_at is in the future")
        metrics = {
            "views": int(row["views"]),
            "impressions": int(row["impressions"]),
            "click_through_rate_percent": float(row["click_through_rate_percent"]),
            "watch_time_minutes": float(row["watch_time_minutes"]),
            "average_view_duration_seconds": float(row["average_view_duration_seconds"]),
            "likes": int(row["likes"]),
            "comments": int(row["comments"]),
            "subscribers_gained": int(row["subscribers_gained"]),
        }
        if any(value < 0 or value > 10**15 for value in metrics.values()):
            raise ValueError("metrics must be between 0 and 1e15")
        if any(not math.isfinite(metrics[key]) for key in ("click_through_rate_percent", "watch_time_minutes", "average_view_duration_seconds")):
            raise ValueError("metrics must be finite numbers")
        if metrics["click_through_rate_percent"] > 100 or metrics["average_view_duration_seconds"] > 86400:
            raise ValueError("CTR or average view duration is outside valid bounds")
        return video_id, collected, metrics
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"CSV line {line_number}: {exc}") from exc


@router.post("/import", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def import_csv(channel_id: UUID = Query(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    channel = db.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel configuration not found")
    payload = await file.read(MAX_CSV_BYTES + 1)
    if len(payload) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="Analytics CSV is limited to 5 MB")
    try:
        decoded = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(decoded))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing CSV columns: {', '.join(sorted(missing))}")
    parsed_rows = []
    seen: set[tuple[str, datetime]] = set()
    for row_number, row in enumerate(reader, start=2):
        if row_number > MAX_ROWS + 1:
            raise HTTPException(status_code=413, detail=f"CSV is limited to {MAX_ROWS} data rows")
        try:
            video_id, collected, metrics = _parse_row(row, row_number)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        key = (video_id, collected)
        if key in seen:
            raise HTTPException(status_code=422, detail=f"CSV line {row_number}: duplicate video_id and collected_at")
        seen.add(key)
        parsed_rows.append((video_id, collected, metrics))
    if not parsed_rows:
        raise HTTPException(status_code=422, detail="CSV contains no data rows")

    import_id = uuid4()
    inserted = 0
    updated = 0
    for video_id, collected, metrics in parsed_rows:
        snapshot = db.scalar(select(AnalyticsSnapshot).where(
            AnalyticsSnapshot.channel_id == channel_id,
            AnalyticsSnapshot.external_video_id == video_id,
            AnalyticsSnapshot.collected_at == collected,
        ))
        if snapshot is None:
            snapshot = AnalyticsSnapshot(channel_id=channel_id, external_video_id=video_id,
                                         collected_at=collected, metrics=metrics, source="user_csv",
                                         import_id=import_id, created_at=utc_now())
            db.add(snapshot)
            inserted += 1
        else:
            snapshot.metrics = metrics
            snapshot.source = "user_csv"
            snapshot.import_id = import_id
            updated += 1
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ImportResult(import_id=import_id, channel_id=channel_id, rows_imported=inserted,
                        rows_updated=updated, rows_total=len(parsed_rows))


@router.get("/channels/{channel_id}", response_model=AnalyticsSummary)
def channel_summary(channel_id: UUID, db: Session = Depends(get_db)):
    if db.get(Channel, channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel configuration not found")
    snapshots = db.scalars(select(AnalyticsSnapshot).where(AnalyticsSnapshot.channel_id == channel_id)
                           .order_by(AnalyticsSnapshot.collected_at.asc())).all()
    latest_by_video: dict[str, AnalyticsSnapshot] = {}
    for snapshot in snapshots:
        current = latest_by_video.get(snapshot.external_video_id)
        if current is None or snapshot.collected_at > current.collected_at:
            latest_by_video[snapshot.external_video_id] = snapshot
    latest = list(latest_by_video.values())
    if not latest:
        return AnalyticsSummary(channel_id=channel_id, video_count=0, sample_size="small",
                                data_window_start=None, latest_snapshot_at=None, views_total=0,
                                impressions_total=0, weighted_ctr_percent=None, watch_time_minutes_total=0,
                                average_view_duration_seconds=None, top_videos=[],
                                interpretation="No imported analytics yet; no performance insight is available.")
    views_total = sum(item.metrics["views"] for item in latest)
    impressions_total = sum(item.metrics["impressions"] for item in latest)
    watch_time_total = sum(item.metrics["watch_time_minutes"] for item in latest)
    weighted_ctr = (sum(item.metrics["click_through_rate_percent"] * item.metrics["impressions"] for item in latest) / impressions_total) if impressions_total else None
    average_view_duration = (sum(item.metrics["average_view_duration_seconds"] * item.metrics["views"] for item in latest) / views_total) if views_total else None
    video_count = len(latest)
    sample_size = "small" if video_count < 10 else "moderate" if video_count < 30 else "larger"
    interpretation = ("Descriptive only: fewer than 10 videos are available, so no strategy recommendation is generated."
                      if video_count < 10 else
                      "Descriptive summary of the imported video sample. It does not establish causality or predict future results.")
    top_videos = [TopVideo(video_id=item.external_video_id, views=item.metrics["views"],
                           average_view_duration_seconds=item.metrics["average_view_duration_seconds"])
                  for item in sorted(latest, key=lambda item: item.metrics["views"], reverse=True)[:10]]
    return AnalyticsSummary(channel_id=channel_id, video_count=video_count, sample_size=sample_size,
                            data_window_start=min(item.collected_at for item in latest),
                            latest_snapshot_at=max(item.collected_at for item in latest), views_total=views_total,
                            impressions_total=impressions_total, weighted_ctr_percent=round(weighted_ctr, 2) if weighted_ctr is not None else None,
                            watch_time_minutes_total=round(watch_time_total, 2),
                            average_view_duration_seconds=round(average_view_duration, 2) if average_view_duration is not None else None,
                            top_videos=top_videos, interpretation=interpretation)
