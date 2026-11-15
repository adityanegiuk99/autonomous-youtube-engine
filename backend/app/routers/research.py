import hashlib
import json
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ResearchDocument, TrendItem, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(require_api_token)])


class ResearchRead(BaseModel):
    id: UUID
    trend_item_id: UUID
    version: int
    document_type: str
    content: dict
    content_hash: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("/trends/{trend_id}", response_model=list[ResearchRead])
def list_source_packs(trend_id: UUID, db: Session = Depends(get_db)):
    if db.get(TrendItem, trend_id) is None:
        raise HTTPException(status_code=404, detail="Trend item not found")
    return db.scalars(select(ResearchDocument).where(ResearchDocument.trend_item_id == trend_id)
                      .order_by(ResearchDocument.version.desc())).all()


@router.post("/trends/{trend_id}/source-packs", response_model=ResearchRead, status_code=status.HTTP_201_CREATED)
def create_source_pack(trend_id: UUID, db: Session = Depends(get_db)):
    trend = db.scalar(select(TrendItem).where(TrendItem.id == trend_id).with_for_update())
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend item not found")
    content = {
        "topic": trend.title,
        "rss_synopsis": trend.summary,
        "synopsis_source_feed": trend.summary_source_url,
        "references": trend.article_urls,
        "observed_in_feeds": trend.source_urls,
        "verification_status": "not_independently_verified",
        "note": "This pack preserves RSS metadata and links. It is not fact-checked research and contains no verified claims.",
    }
    version = (db.scalar(select(func.max(ResearchDocument.version)).where(ResearchDocument.trend_item_id == trend_id)) or 0) + 1
    serialized = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    document = ResearchDocument(id=uuid4(), trend_item_id=trend_id, version=version, document_type="rss_source_pack",
                                content=content, content_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
                                created_at=utc_now())
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
