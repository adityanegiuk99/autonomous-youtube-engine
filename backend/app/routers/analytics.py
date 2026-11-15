import csv
import io
import math
import re
import statistics
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AnalyticsSnapshot, Channel, ContentExperiment, utc_now
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


class LearningSignal(BaseModel):
    metric: str
    top_view_group_median: float
    lower_view_group_median: float
    difference_percent: float | None
    direction: str


class LearningInsights(BaseModel):
    channel_id: UUID
    video_count: int
    evidence_strength: str
    basis: str
    caveat: str
    signals: list[LearningSignal]
    suggested_review: str | None


ExperimentMetric = Literal["views", "click_through_rate_percent", "average_view_duration_seconds",
                           "watch_time_minutes", "likes", "comments", "subscribers_gained"]
ExperimentStatus = Literal["planned", "running", "completed", "cancelled"]


class ExperimentCreate(BaseModel):
    channel_id: UUID
    title: str = Field(min_length=1, max_length=120)
    hypothesis: str = Field(min_length=1, max_length=5000)
    variable: str = Field(min_length=1, max_length=80)
    control_description: str = Field(min_length=1, max_length=500)
    treatment_description: str = Field(min_length=1, max_length=500)
    metric: ExperimentMetric
    control_video_ids: list[str] = Field(min_length=1, max_length=100)
    treatment_video_ids: list[str] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)


class ExperimentUpdate(BaseModel):
    status: ExperimentStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ExperimentRead(BaseModel):
    id: UUID
    channel_id: UUID
    title: str
    hypothesis: str
    variable: str
    control_description: str
    treatment_description: str
    metric: ExperimentMetric
    control_video_ids: list[str]
    treatment_video_ids: list[str]
    status: ExperimentStatus
    notes: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    control_sample_size: int
    treatment_sample_size: int
    control_median: float | None
    treatment_median: float | None
    difference_percent: float | None
    caveat: str
    model_config = ConfigDict(from_attributes=True)


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


@router.get("/channels/{channel_id}/insights", response_model=LearningInsights)
def channel_learning_insights(channel_id: UUID, db: Session = Depends(get_db)):
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
    count = len(latest)
    strength = "insufficient" if count < 10 else "low" if count < 30 else "moderate"
    caveat = ("Exploratory description of user-imported cumulative snapshots. It is not causal or predictive and does not adjust for video age, format, topic, or promotion. Evidence strength reflects sample count only."
              if count >= 10 else
              "Fewer than 10 videos are available. This sample is too small for a useful comparison; no recommendation is generated.")
    if count < 10:
        return LearningInsights(channel_id=channel_id, video_count=count, evidence_strength=strength,
                                basis="latest snapshot per imported video", caveat=caveat, signals=[],
                                suggested_review=None)

    ranked = sorted(latest, key=lambda item: item.metrics["views"], reverse=True)
    group_size = max(2, math.ceil(count * 0.25))
    top_group, lower_group = ranked[:group_size], ranked[-group_size:]
    signals = []
    for key, label in (("click_through_rate_percent", "click-through rate"),
                        ("average_view_duration_seconds", "average view duration")):
        top_median = statistics.median(item.metrics[key] for item in top_group)
        lower_median = statistics.median(item.metrics[key] for item in lower_group)
        if top_median == lower_median:
            continue
        difference = (round((top_median - lower_median) / lower_median * 100, 1)
                      if lower_median > 0 else None)
        signals.append(LearningSignal(metric=label, top_view_group_median=round(top_median, 2),
                                      lower_view_group_median=round(lower_median, 2),
                                      difference_percent=difference,
                                      direction="higher" if top_median > lower_median else "lower"))
    suggested_review = ("Review the titles, topics, hooks, formats, and publish timing in both groups. If you find a repeatable editorial pattern, record one controlled experiment and compare it with future imports. Treat these signals as hypotheses, not instructions to change strategy."
                       if signals else None)
    return LearningInsights(channel_id=channel_id, video_count=count, evidence_strength=strength,
                            basis=f"Latest snapshot per video; compared the {group_size} highest-view and {group_size} lowest-view videos",
                            caveat=caveat, signals=signals, suggested_review=suggested_review)


def _latest_channel_snapshots(channel_id: UUID, db: Session) -> dict[str, AnalyticsSnapshot]:
    snapshots = db.scalars(select(AnalyticsSnapshot).where(AnalyticsSnapshot.channel_id == channel_id)
                           .order_by(AnalyticsSnapshot.collected_at.asc())).all()
    latest: dict[str, AnalyticsSnapshot] = {}
    for snapshot in snapshots:
        previous = latest.get(snapshot.external_video_id)
        if previous is None or snapshot.collected_at > previous.collected_at:
            latest[snapshot.external_video_id] = snapshot
    return latest


def _experiment_read(experiment: ContentExperiment, latest: dict[str, AnalyticsSnapshot]) -> ExperimentRead:
    metric = experiment.metric
    control = [latest[video_id].metrics[metric] for video_id in experiment.control_video_ids if video_id in latest]
    treatment = [latest[video_id].metrics[metric] for video_id in experiment.treatment_video_ids if video_id in latest]
    control_median = statistics.median(control) if control else None
    treatment_median = statistics.median(treatment) if treatment else None
    difference = (round((treatment_median - control_median) / control_median * 100, 1)
                  if control_median is not None and treatment_median is not None and control_median > 0 else None)
    return ExperimentRead(
        id=experiment.id, channel_id=experiment.channel_id, title=experiment.title,
        hypothesis=experiment.hypothesis, variable=experiment.variable,
        control_description=experiment.control_description,
        treatment_description=experiment.treatment_description, metric=metric,
        control_video_ids=experiment.control_video_ids,
        treatment_video_ids=experiment.treatment_video_ids, status=experiment.status,
        notes=experiment.notes, created_at=experiment.created_at,
        started_at=experiment.started_at, finished_at=experiment.finished_at,
        control_sample_size=len(control), treatment_sample_size=len(treatment),
        control_median=round(control_median, 2) if control_median is not None else None,
        treatment_median=round(treatment_median, 2) if treatment_median is not None else None,
        difference_percent=difference,
        caveat="Descriptive medians from the latest imported snapshot per listed video. Group assignment was manual; results are not causal and may reflect video age, topic, format, promotion, or other differences.",
    )


def _validate_experiment_groups(control: list[str], treatment: list[str]) -> None:
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) for video_id in control + treatment):
        raise HTTPException(status_code=422, detail="Experiment groups must contain valid 11-character YouTube video IDs")
    if len(set(control)) != len(control) or len(set(treatment)) != len(treatment):
        raise HTTPException(status_code=422, detail="A video ID cannot be repeated within an experiment group")
    if set(control) & set(treatment):
        raise HTTPException(status_code=422, detail="Control and treatment video groups must not overlap")


@router.get("/channels/{channel_id}/experiments", response_model=list[ExperimentRead])
def list_experiments(channel_id: UUID, db: Session = Depends(get_db)):
    if db.get(Channel, channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel configuration not found")
    latest = _latest_channel_snapshots(channel_id, db)
    experiments = db.scalars(select(ContentExperiment).where(
        ContentExperiment.channel_id == channel_id,
    ).order_by(ContentExperiment.created_at.desc()).limit(100)).all()
    return [_experiment_read(experiment, latest) for experiment in experiments]


@router.post("/experiments", response_model=ExperimentRead, status_code=201)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    if db.get(Channel, payload.channel_id) is None:
        raise HTTPException(status_code=404, detail="Channel configuration not found")
    required_text = (payload.title, payload.hypothesis, payload.variable,
                     payload.control_description, payload.treatment_description)
    if any(not value.strip() for value in required_text):
        raise HTTPException(status_code=422, detail="Experiment name, hypothesis, variable, and group descriptions cannot be blank")
    _validate_experiment_groups(payload.control_video_ids, payload.treatment_video_ids)
    selected_ids = set(payload.control_video_ids + payload.treatment_video_ids)
    foreign_ids = set(db.scalars(select(AnalyticsSnapshot.external_video_id).where(
        AnalyticsSnapshot.external_video_id.in_(selected_ids),
        AnalyticsSnapshot.channel_id != payload.channel_id,
    )).all())
    channel_ids = set(db.scalars(select(AnalyticsSnapshot.external_video_id).where(
        AnalyticsSnapshot.external_video_id.in_(selected_ids),
        AnalyticsSnapshot.channel_id == payload.channel_id,
    )).all())
    if foreign_ids - channel_ids:
        raise HTTPException(status_code=422, detail="A selected video has analytics imported under another channel")
    experiment = ContentExperiment(
        channel_id=payload.channel_id, title=payload.title.strip(),
        hypothesis=payload.hypothesis.strip(), variable=payload.variable.strip(),
        control_description=payload.control_description.strip(),
        treatment_description=payload.treatment_description.strip(), metric=payload.metric,
        control_video_ids=payload.control_video_ids,
        treatment_video_ids=payload.treatment_video_ids, status="planned",
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return _experiment_read(experiment, _latest_channel_snapshots(payload.channel_id, db))


@router.patch("/experiments/{experiment_id}", response_model=ExperimentRead)
def update_experiment(experiment_id: UUID, payload: ExperimentUpdate, db: Session = Depends(get_db)):
    experiment = db.get(ContentExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if "notes" in payload.model_fields_set:
        experiment.notes = payload.notes.strip() if payload.notes else None
    if payload.status is not None and payload.status != experiment.status:
        transitions = {"planned": {"running", "cancelled"}, "running": {"completed", "cancelled"},
                       "completed": set(), "cancelled": set()}
        if payload.status not in transitions[experiment.status]:
            raise HTTPException(status_code=409, detail=f"Experiment cannot move from {experiment.status} to {payload.status}")
        experiment.status = payload.status
        now = utc_now()
        if payload.status == "running":
            experiment.started_at = now
        if payload.status in ("completed", "cancelled"):
            experiment.finished_at = now
    db.commit()
    db.refresh(experiment)
    return _experiment_read(experiment, _latest_channel_snapshots(experiment.channel_id, db))
