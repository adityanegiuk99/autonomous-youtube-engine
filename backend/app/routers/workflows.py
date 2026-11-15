from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ContentIdea, WorkflowEvent
from app.security import require_api_token

router = APIRouter(prefix="/workflows", tags=["workflows"], dependencies=[Depends(require_api_token)])


class WorkflowEventRead(BaseModel):
    id: UUID
    content_idea_id: UUID
    previous_state: str | None
    state: str
    event_type: str
    actor: str
    reason: str
    metadata: dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_event(cls, event: WorkflowEvent) -> "WorkflowEventRead":
        return cls(id=event.id, content_idea_id=event.content_idea_id,
                   previous_state=event.previous_state, state=event.state,
                   event_type=event.event_type, actor=event.actor, reason=event.reason,
                   metadata=event.metadata_json, created_at=event.created_at)


class WorkflowTimeline(BaseModel):
    content_idea_id: UUID
    current_state: str
    events: list[WorkflowEventRead]


@router.get("/ideas/{idea_id}/events", response_model=WorkflowTimeline)
def idea_workflow_events(idea_id: UUID, limit: int = Query(default=100, ge=1, le=500),
                         db: Session = Depends(get_db)):
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(status_code=404, detail="Content idea not found")
    recent = db.scalars(select(WorkflowEvent).where(WorkflowEvent.content_idea_id == idea_id)
                        .order_by(WorkflowEvent.created_at.desc(), WorkflowEvent.id.desc()).limit(limit)).all()
    chronological = list(reversed(recent))
    events = [WorkflowEventRead.from_event(event) for event in chronological]
    return WorkflowTimeline(content_idea_id=idea_id, current_state=idea.status, events=events)
