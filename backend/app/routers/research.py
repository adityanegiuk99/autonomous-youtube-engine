import hashlib
import json
from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
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


class EvidenceReference(BaseModel):
    source_url: str = Field(min_length=1, max_length=2048)
    source_title: str = Field(min_length=1, max_length=300)
    excerpt: str | None = Field(default=None, max_length=2000)

    @field_validator("source_url")
    @classmethod
    def public_https_link(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Citation URLs must be HTTPS links without embedded credentials")
        return value


class ClaimAssessment(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    assessment: Literal["unreviewed", "human_supports_cited_sources", "human_found_conflict", "human_found_insufficient_support"] = "unreviewed"
    assessment_note: str | None = Field(default=None, max_length=2000)
    references: list[EvidenceReference] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def explain_human_assessment(self):
        if self.assessment != "unreviewed" and not (self.assessment_note or "").strip():
            raise ValueError("A note is required for a human assessment")
        return self


class ManualDossierCreate(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    claims: list[ClaimAssessment] = Field(min_length=1, max_length=50)
    open_questions: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("open_questions")
    @classmethod
    def bound_questions(cls, values: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 500 for item in values):
            raise ValueError("Open questions must contain 1 to 500 characters")
        return values


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


@router.post("/trends/{trend_id}/dossiers", response_model=ResearchRead, status_code=status.HTTP_201_CREATED)
def create_manual_dossier(trend_id: UUID, payload: ManualDossierCreate, db: Session = Depends(get_db)):
    trend = db.scalar(select(TrendItem).where(TrendItem.id == trend_id).with_for_update())
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend item not found")
    content = {
        "topic": trend.title,
        "summary": payload.summary,
        "claims": [claim.model_dump() for claim in payload.claims],
        "open_questions": payload.open_questions,
        "assessment_basis": "human_entered",
        "note": "Human-entered evidence map. AYE has not independently checked claims, excerpts, or citation URLs.",
    }
    version = (db.scalar(select(func.max(ResearchDocument.version)).where(ResearchDocument.trend_item_id == trend_id)) or 0) + 1
    serialized = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    document = ResearchDocument(id=uuid4(), trend_item_id=trend_id, version=version,
                                document_type="manual_research_dossier", content=content,
                                content_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(), created_at=utc_now())
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
