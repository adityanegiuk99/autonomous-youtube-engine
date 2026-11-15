import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WorkflowEvent, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/operations", tags=["operations"], dependencies=[Depends(require_api_token)])


class RenderUsageSummary(BaseModel):
    period_days: int
    starts_at: datetime
    ends_at: datetime
    attempts: int
    measured_attempts: int
    unmeasured_attempts: int
    technical_qa_passes: int
    technical_qa_failures: int
    render_failures: int
    render_seconds_total: float
    render_seconds_average: float | None
    source_media_bytes: int
    rendered_video_bytes: int
    monetary_cost_available: bool = False
    note: str


def _number(metadata: dict, key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric >= 0 else None


@router.get("/render-usage", response_model=RenderUsageSummary)
def render_usage(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    ends_at = utc_now()
    starts_at = ends_at - timedelta(days=days)
    events = db.scalars(select(WorkflowEvent).where(
        WorkflowEvent.created_at >= starts_at,
        WorkflowEvent.event_type.in_(("production_failed", "production_rendered")),
    ).order_by(WorkflowEvent.created_at.asc())).all()

    render_seconds: list[float] = []
    source_bytes = 0
    video_bytes = 0
    measured_attempts = 0
    qa_passes = 0
    qa_failures = 0
    render_failures = 0
    for event in events:
        metadata = event.metadata_json or {}
        duration = _number(metadata, "render_duration_seconds")
        source_size = _number(metadata, "source_bytes")
        output_size = _number(metadata, "output_bytes")
        if duration is not None and source_size is not None:
            measured_attempts += 1
            render_seconds.append(duration)
            source_bytes += int(source_size)
        if output_size is not None:
            video_bytes += int(output_size)
        if event.event_type == "production_failed":
            render_failures += 1
        else:
            outcome = metadata.get("technical_qa_status")
            if outcome == "TECHNICAL_QA_PASSED":
                qa_passes += 1
            elif outcome == "TECHNICAL_QA_FAILED":
                qa_failures += 1

    attempts = len(events)
    total_seconds = round(sum(render_seconds), 3)
    return RenderUsageSummary(
        period_days=days, starts_at=starts_at, ends_at=ends_at,
        attempts=attempts, measured_attempts=measured_attempts,
        unmeasured_attempts=attempts - measured_attempts,
        technical_qa_passes=qa_passes, technical_qa_failures=qa_failures,
        render_failures=render_failures, render_seconds_total=total_seconds,
        render_seconds_average=round(total_seconds / measured_attempts, 3) if measured_attempts else None,
        source_media_bytes=source_bytes, rendered_video_bytes=video_bytes,
        note="Shows local render time and media volume from recorded events. No provider/API spend or rupee cost is configured, so financial cost is unavailable.",
    )
