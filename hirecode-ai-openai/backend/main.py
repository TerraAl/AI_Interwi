from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

import uvicorn
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

import redis.asyncio as redis

from anticheat import AntiCheatService
from ai_interviewer import AIInterviewer, InterviewContext
from adaptive import AdaptiveEngine
from judge import SubmissionJudge
from code_quality import analyze_code
from models import Base, EngineLocal, SessionLocal, SessionModel
from runner import SupportedLanguage
from schemas import (
    AdminTaskCreate,
    AdminTaskResponse,
    InterviewEvent,
    InterviewInitRequest,
    InterviewInitResponse,
    SubmissionRequest,
    SubmissionResponse,
)
from websocket_manager import WebsocketManager

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = PROJECT_ROOT.parent / "frontend" / "dist"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def get_db() -> AsyncIterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=EngineLocal)
    yield


app = FastAPI(lifespan=lifespan, title="HireCode AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

ws_manager = WebsocketManager()
anticheat_service = AntiCheatService()
adaptive_engine = AdaptiveEngine()
async def log_chat(session_id: str, role: str, message: str) -> None:
    await redis_client.rpush(
        f"session:{session_id}:chat",
        json.dumps({"role": role, "message": message}),
    )


ai = AIInterviewer(manager=ws_manager, chat_logger=log_chat)
judge = SubmissionJudge()


class SessionStartResponse(BaseModel):
    session_id: str
    task: Dict[str, Any]


class AdminSessionResponse(BaseModel):
    sessions: list[dict[str, Any]]


@app.post("/api/interview/start", response_model=SessionStartResponse)
async def start_interview(
    payload: InterviewInitRequest, db: Session = Depends(get_db)
) -> SessionStartResponse:
    task = adaptive_engine.pick_task(payload.stack)
    if not task:
        raise HTTPException(status_code=404, detail="No tasks available")

    session_db = SessionModel.create_from_request(db, payload, task)
    anticheat_service.bootstrap_session(session_db.id)
    await redis_client.hset(
        f"session:{session_db.id}",
        mapping={
            "candidate": payload.candidate_name,
            "stack": payload.stack,
            "task_id": task["id"],
        },
    )

    return SessionStartResponse(session_id=str(session_db.id), task=task)


@app.post("/api/interview/submit", response_model=SubmissionResponse)
async def submit_solution(
    payload: SubmissionRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    try:
        session_db = SessionModel.get_or_404(db, payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    language = SupportedLanguage(payload.language)

    judge_result = await judge.evaluate(payload.code, language, payload.task_id)
    judge_result["code_quality"] = analyze_code(payload.code, payload.language)
    anticheat = anticheat_service.snapshot(payload.session_id)
    await redis_client.hset(
        f"session:{payload.session_id}",
        mapping={"latest_result": json.dumps(judge_result)},
    )
    background.add_task(
        ai.capture_judge_feedback,
        payload.session_id,
        judge_result,
        anticheat,
    )
    session_db.update_from_result(db, judge_result, anticheat)
    return judge_result


@app.post("/api/admin/tasks", response_model=AdminTaskResponse)
async def create_task(payload: AdminTaskCreate) -> AdminTaskResponse:
    task = adaptive_engine.save_task(payload)
    return AdminTaskResponse(task=task)


@app.get("/api/admin/sessions", response_model=AdminSessionResponse)
async def list_sessions(db: Session = Depends(get_db)) -> AdminSessionResponse:
    sessions = SessionModel.list_recent(db)
    return AdminSessionResponse(sessions=sessions)


@app.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: str) -> None:
    await ws_manager.connect(session_id, websocket)
    try:
        await websocket.accept()
        await websocket.send_json({"type": "connected", "session_id": session_id})

        async for message in websocket.iter_text():
            data = json.loads(message)
            event = InterviewEvent(**data)
            anticheat_service.record_event(session_id, event)
            snapshot = anticheat_service.snapshot(session_id)

            if event.type == "chat:user":
                await log_chat(session_id, "user", event.payload.get("message", ""))
                asyncio.create_task(
                    ai.stream_reply(
                        session_id=session_id,
                        ws_manager=ws_manager,
                        context=InterviewContext.from_event(event),
                    )
                )
            elif event.type == "code:update":
                ai.cache_code_snapshot(session_id, event.payload.get("content", ""))
                await redis_client.hset(
                    f"session:{session_id}",
                    mapping={"latest_code": event.payload.get("content", "")},
                )
            elif event.type.startswith("anticheat:"):
                await ws_manager.broadcast(
                    session_id,
                    {
                        "type": "anticheat",
                        "trust_score": snapshot.trust_score,
                        "events": snapshot.events,
                    },
                )
                await redis_client.hset(
                    f"session:{session_id}",
                    mapping={"trust_score": snapshot.trust_score},
                )
                if event.type == "anticheat:paste" and event.payload.get("chars", 0) >= 600:
                    warning = "Заметил большую вставку кода. Это твоё решение или ты воспользовался помощью?"
                    await ws_manager.broadcast(
                        session_id,
                        {"type": "chat:ai", "message": warning, "meta": {"severity": "warning"}},
                    )
                    await log_chat(session_id, "ai", warning)
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
    finally:
        anticheat_service.complete_session(session_id)


def run() -> None:
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))


if __name__ == "__main__":
    run()

