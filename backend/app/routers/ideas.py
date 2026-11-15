from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, ContentIdea, TrendItem, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/ideas", tags=["ideas"], dependencies=[Depends(require_api_token)])


class IdeaCreate(BaseModel):
    channel_id: UUID
    trend_item_id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    format: Literal["short", "long"]
    engagement_potential: float = Field(ge=0, le=100, description="Human estimate; this is not measured analytics")
    audience_relevance: float = Field(ge=0, le=100)
    originality: float = Field(ge=0, le=100)
    research_quality: float = Field(ge=0, le=100)
    competition: float | None = Field(default=None, ge=0, le=100)


class IdeaRead(BaseModel):
    id: UUID
    channel_id: UUID
    trend_item_id: UUID | None
    title: str
    format: str
    trend_velocity: float
    engagement_potential: float
    audience_relevance: float
    originality: float
    research_quality: float
    competition: float | None
    opportunity_score: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def score_opportunity(trend: float, engagement: float, audience: float, originality: float, research: float) -> float:
    return round(0.30 * trend + 0.20 * engagement + 0.20 * audience + 0.15 * originality + 0.15 * research, 2)


@router.get("", response_model=list[IdeaRead])
def list_ideas(channel_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    query = select(ContentIdea).order_by(ContentIdea.opportunity_score.desc(), ContentIdea.created_at.desc()).limit(limit)
    if channel_id is not None:
        query = query.where(ContentIdea.channel_id == channel_id)
    return db.scalars(query).all()


@router.post("", response_model=IdeaRead, status_code=status.HTTP_201_CREATED)
def create_idea(payload: IdeaCreate, db: Session = Depends(get_db)):
    channel = db.get(Channel, payload.channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    trend = db.get(TrendItem, payload.trend_item_id) if payload.trend_item_id else None
    if payload.trend_item_id and trend is None:
        raise HTTPException(status_code=404, detail="Trend item not found")
    trend_velocity = trend.trend_score if trend else 0.0
    idea = ContentIdea(**payload.model_dump(), trend_velocity=trend_velocity,
                       opportunity_score=score_opportunity(trend_velocity, payload.engagement_potential,
                                                          payload.audience_relevance, payload.originality,
                                                          payload.research_quality),
                       status="DISCOVERED", created_at=utc_now())
    db.add(idea)
    db.commit()
    db.refresh(idea)
    return idea
