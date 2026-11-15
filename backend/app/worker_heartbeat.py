"""Worker liveness snapshots shared with the Operations API."""

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from uuid import UUID

from app.database import SessionLocal
from app.models import WorkerHeartbeat, utc_now


@dataclass
class WorkerState:
    started_at: datetime = field(default_factory=utc_now)
    _current_attempt_id: UUID | None = None
    _lock: Lock = field(default_factory=Lock)

    def set_attempt(self, attempt_id: UUID | None) -> None:
        with self._lock:
            self._current_attempt_id = attempt_id

    def current_attempt(self) -> UUID | None:
        with self._lock:
            return self._current_attempt_id


def record_worker_heartbeat(worker_id: str, state: WorkerState) -> None:
    now = utc_now()
    with SessionLocal() as db:
        heartbeat = db.get(WorkerHeartbeat, worker_id)
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(worker_id=worker_id, started_at=state.started_at,
                                        last_seen_at=now, current_attempt_id=state.current_attempt())
            db.add(heartbeat)
        else:
            heartbeat.last_seen_at = now
            heartbeat.current_attempt_id = state.current_attempt()
        db.commit()
