from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    niche: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    target_country: Mapped[str | None] = mapped_column(String(2))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class TrendItem(Base):
    __tablename__ = "trend_items"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    canonical_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_source_url: Mapped[str | None] = mapped_column(String(2048))
    source_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    article_urls: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class ResearchDocument(Base):
    __tablename__ = "research_documents"
    __table_args__ = (UniqueConstraint("trend_item_id", "version", name="uq_research_trend_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    trend_item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trend_items.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="RESTRICT"), nullable=False, index=True)
    trend_item_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("trend_items.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    trend_velocity: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_potential: Mapped[float] = mapped_column(Float, nullable=False)
    audience_relevance: Mapped[float] = mapped_column(Float, nullable=False)
    originality: Mapped[float] = mapped_column(Float, nullable=False)
    research_quality: Mapped[float] = mapped_column(Float, nullable=False)
    competition: Mapped[float | None] = mapped_column(Float)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ScriptVersion(Base):
    __tablename__ = "scripts"
    __table_args__ = (UniqueConstraint("content_idea_id", "version", name="uq_scripts_idea_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    content_idea_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("content_ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False, default="human")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StoryboardVersion(Base):
    __tablename__ = "storyboards"
    __table_args__ = (UniqueConstraint("content_idea_id", "version", name="uq_storyboards_idea_version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    content_idea_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("content_ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    script_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scripts.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    scenes: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    storage_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    license_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class RenderedVideo(Base):
    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    content_idea_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("content_ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    storyboard_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("storyboards.id", ondelete="RESTRICT"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[int] = mapped_column(nullable=False)
    height: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PREVIEW_RENDERED")
    video_type: Mapped[str] = mapped_column(String(24), nullable=False, default="animatic")
    thumbnail_key: Mapped[str | None] = mapped_column(String(80))
    media_manifest: Mapped[list[dict] | None] = mapped_column(JSON)
    qa_report: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ProductionAttempt(Base):
    __tablename__ = "production_attempts"
    __table_args__ = (
        Index("ix_production_attempts_storyboard_started", "content_idea_id", "storyboard_version_id", "started_at"),
        Index("uq_production_attempts_active", "content_idea_id", "storyboard_version_id", unique=True,
              postgresql_where=text("status IN ('queued', 'running')"),
              sqlite_where=text("status IN ('queued', 'running')")),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    content_idea_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("content_ideas.id", ondelete="CASCADE"), nullable=False)
    storyboard_version_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("storyboards.id", ondelete="RESTRICT"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    video_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("videos.id", ondelete="SET NULL"))
    render_duration_seconds: Mapped[float | None] = mapped_column(Float)
    source_bytes: Mapped[int | None] = mapped_column(BigInteger)
    output_bytes: Mapped[int | None] = mapped_column(BigInteger)
    failure_class: Mapped[str | None] = mapped_column(String(48))


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    video_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("videos.id", ondelete="RESTRICT"), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    review_checks: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    __table_args__ = (UniqueConstraint("video_id", name="uq_publish_jobs_video"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    video_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("videos.id", ondelete="RESTRICT"), nullable=False, index=True)
    approval_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("approvals.id", ondelete="RESTRICT"), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="RESTRICT"), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled_local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (UniqueConstraint("channel_id", "external_video_id", "collected_at", name="uq_analytics_channel_video_date"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="RESTRICT"), nullable=False, index=True)
    external_video_id: Mapped[str] = mapped_column(String(128), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="user_csv")
    import_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_type_created", "event_type", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    content_idea_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("content_ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
