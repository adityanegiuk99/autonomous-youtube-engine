from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import WorkflowEvent, utc_now


def record_workflow_event(db: Session, content_idea_id: UUID, state: str, event_type: str,
                          reason: str, metadata: dict[str, Any] | None = None,
                          previous_state: str | None = None,
                          actor: str = "local-owner") -> None:
    """Append a workflow audit event in the caller's transaction."""
    db.add(WorkflowEvent(content_idea_id=content_idea_id, previous_state=previous_state,
                         state=state, event_type=event_type,
                         actor=actor, reason=reason, metadata_json=metadata or {}, created_at=utc_now()))
