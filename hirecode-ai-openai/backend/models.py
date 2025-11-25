from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

from sqlalchemy import JSON, Column, DateTime, Float, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

if TYPE_CHECKING:
    from schemas import InterviewInitRequest
    from anticheat import AntiCheatSnapshot

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres:5432/hirecode"
)


class Base(DeclarativeBase):
    pass


EngineLocal = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=EngineLocal, autocommit=False, autoflush=False)


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate: Mapped[str] = mapped_column(String)
    stack: Mapped[str] = mapped_column(String)
    task_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    trust_score: Mapped[float] = mapped_column(Float, default=100.0)
    summary: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @classmethod
    def create_from_request(
        cls, db: Session, payload: "InterviewInitRequest", task: Dict[str, Any]
    ) -> "SessionModel":
        session = cls(
            candidate=payload.candidate_name,
            stack=payload.stack,
            task_id=task["id"],
            status="active",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @classmethod
    def get_or_404(cls, db: Session, session_id: str) -> "SessionModel":
        session = db.get(cls, session_id)
        if not session:
            raise ValueError("Session not found")
        return session

    def update_from_result(
        self, db: Session, judge_result: Dict[str, Any], anticheat: "AntiCheatSnapshot"
    ) -> None:
        self.status = "passed" if judge_result["passed"] else "failed"
        self.trust_score = anticheat.trust_score
        self.summary = {
            "judge_result": judge_result,
            "anticheat": anticheat.__dict__,
        }
        db.add(self)
        db.commit()

    @classmethod
    def list_recent(cls, db: Session) -> List[Dict[str, Any]]:
        stmt = select(cls).order_by(cls.created_at.desc()).limit(50)
        results = db.execute(stmt).scalars().all()
        return [
            {
                "id": row.id,
                "candidate": row.candidate,
                "stack": row.stack,
                "status": row.status,
                "trust_score": row.trust_score,
                "summary": row.summary,
                "created_at": row.created_at.isoformat(),
            }
            for row in results
        ]

