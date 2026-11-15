from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, ContentIdea, RenderedVideo, TrendItem
from app.security import require_api_token

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_api_token)])


class RecentIdea(BaseModel):
    id: UUID
    title: str
    format: Literal["short", "long"]
    status: str
    opportunity_score: float
    model_config = ConfigDict(from_attributes=True)


class RecentTrend(BaseModel):
    id: UUID
    title: str
    trend_score: float
    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    configured_channels: int
    active_channels: int
    tracked_trends: int
    content_ideas: int
    production_renders: int
    qa_passed_without_decision_renders: int
    qa_failed_renders: int
    recent_ideas: list[RecentIdea]
    recent_trends: list[RecentTrend]


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    configured_channels = db.scalar(select(func.count()).select_from(Channel)) or 0
    active_channels = db.scalar(select(func.count()).select_from(Channel).where(Channel.is_active.is_(True))) or 0
    tracked_trends = db.scalar(select(func.count()).select_from(TrendItem)) or 0
    content_ideas = db.scalar(select(func.count()).select_from(ContentIdea)) or 0
    production_renders = db.scalar(select(func.count()).select_from(RenderedVideo).where(
        RenderedVideo.video_type == "production")) or 0
    production_videos = db.scalars(select(RenderedVideo).where(RenderedVideo.video_type == "production")).all()
    qa_passed_unreviewed = sum(1 for video in production_videos if video.status == "TECHNICAL_QA_PASSED"
                               and video.qa_report and video.qa_report.get("status") == "TECHNICAL_QA_PASSED")
    qa_failed = sum(1 for video in production_videos if video.qa_report
                    and video.qa_report.get("status") == "TECHNICAL_QA_FAILED")
    ideas = db.scalars(select(ContentIdea).order_by(ContentIdea.created_at.desc()).limit(5)).all()
    trends = db.scalars(select(TrendItem).order_by(TrendItem.trend_score.desc(), TrendItem.first_seen_at.desc()).limit(5)).all()
    return DashboardSummary(
        configured_channels=configured_channels, active_channels=active_channels,
        tracked_trends=tracked_trends, content_ideas=content_ideas,
        production_renders=production_renders, qa_passed_without_decision_renders=qa_passed_unreviewed,
        qa_failed_renders=qa_failed,
        recent_ideas=[RecentIdea.model_validate(idea) for idea in ideas],
        recent_trends=[RecentTrend.model_validate(trend) for trend in trends],
    )
