import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from datetime import datetime

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import uvicorn

from models import Base, User, InterviewSession, Task
from schemas import (
    UserCreate, UserLogin, User as UserSchema,
    TaskCreate, Task as TaskSchema,
    InterviewSessionCreate, InterviewSession as SessionSchema,
    WSMessage, CodeUpdateMessage, AntiCheatAlertMessage, AIChatMessage,
    InterviewInitRequest, SessionStartResponse, SubmissionRequest, SubmissionResponse,
    InterviewEvent, AdminTaskCreate
)
from ai_interviewer import AIInterviewer, InterviewContext
from anticheat import AntiCheatService
from adaptive import AdaptiveEngine
from code_quality import CodeQualityAnalyzer
from judge import SubmissionJudge
from websocket_manager import WebsocketManager
from runner import SupportedLanguage

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/hirecode")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# Database setup
print(f"Connecting to database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'hidden'}")
engine = create_async_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Redis setup
redis_client = redis.from_url(REDIS_URL)

# Managers
ws_manager = WebsocketManager()
anticheat_service = AntiCheatService()
adaptive_engine = AdaptiveEngine()
code_quality_analyzer = CodeQualityAnalyzer()
judge = SubmissionJudge()

# Initialize AI interviewer with manager
async def log_chat(session_id: str, role: str, message: str):
    """Log chat message to database"""
    pass

ai = AIInterviewer(manager=ws_manager, chat_logger=log_chat)

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - retry connection to database
    max_retries = 10
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
    
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan, title="HireCode AI API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# Auth dependency (simplified)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    # Simplified auth - in production use proper JWT
    token = credentials.credentials
    # For demo purposes, accept any token and return demo user
    user = await db.get(User, 1)
    if not user:
        user = User(email="demo@hirecode.ai", hashed_password="demo")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

# WebSocket connections storage
active_connections: Dict[int, WebSocket] = {}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.post("/auth/login", response_model=UserSchema)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    # Simplified login
    user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = user.scalar_one_or_none()

    if not user:
        user = User(email=user_data.email, hashed_password=user_data.password)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user

@app.post("/sessions", response_model=SessionSchema)
async def create_session(
    session_data: InterviewSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get first task for user
    first_task = await adaptive_selector.select_first_task(db, current_user.id)

    session = InterviewSession(
        user_id=current_user.id,
        current_task_id=first_task.id if first_task else None,
        user_elo=session_data.user_elo
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session

@app.get("/tasks", response_model=List[TaskSchema])
async def get_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks

@app.post("/tasks", response_model=TaskSchema)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")

    task = Task(**task_data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

# Interview API endpoints
@app.post("/api/interview/start", response_model=SessionStartResponse)
async def start_interview(
    payload: InterviewInitRequest, db: AsyncSession = Depends(get_db)
) -> SessionStartResponse:
    task = adaptive_engine.pick_task(payload.stack)
    if not task:
        raise HTTPException(status_code=404, detail="No tasks available")

    # Get or create demo user
    result = await db.execute(select(User).where(User.email == "demo@hirecode.ai"))
    user = result.scalar_one_or_none()
    if not user:
        user = User(email="demo@hirecode.ai", hashed_password="demo", is_admin=False)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Create session in database
    session = InterviewSession(
        user_id=user.id,
        current_task_id=None,
        user_elo=1200.0,
        started_at=datetime.utcnow()
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    session_id = str(session.id)
    anticheat_service.bootstrap_session(session_id)
    await redis_client.hset(
        f"session:{session_id}",
        mapping={
            "candidate": payload.candidate_name,
            "stack": payload.stack,
            "task_id": task["id"],
        },
    )
    return SessionStartResponse(session_id=session_id, task=task)

@app.post("/api/interview/submit", response_model=SubmissionResponse)
async def submit_solution(
    payload: SubmissionRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    try:
        session = await db.get(InterviewSession, int(payload.session_id))
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid session ID")
    
    language = SupportedLanguage(payload.language)
    judge_result = await judge.evaluate(payload.code, language, payload.task_id)
    judge_result["code_quality"] = code_quality_analyzer.analyze(payload.code, payload.language)
    anticheat = anticheat_service.snapshot(payload.session_id)
    await redis_client.hset(
        f"session:{payload.session_id}",
        mapping={"latest_result": json.dumps(judge_result)},
    )
    
    # Capture AI feedback
    asyncio.create_task(
        ai.capture_judge_feedback(payload.session_id, judge_result, anticheat)
    )
    
    # Update session
    session.total_score = judge_result.get("metrics", {}).get("max_elapsed_ms", 0)
    session.trust_score = anticheat.trust_score
    await db.commit()
    
    return SubmissionResponse(
        passed=judge_result["passed"],
        visible_tests=judge_result["visible_tests"],
        hidden_tests=[],
        code_quality=judge_result["code_quality"],
        metrics=judge_result["metrics"]
    )

@app.post("/api/admin/tasks")
async def create_task_admin(payload: AdminTaskCreate):
    task_data = adaptive_engine.save_task(payload)
    return task_data

@app.get("/api/admin/sessions")
async def list_sessions():
    sessions = []
    # Get all session keys from Redis
    keys = await redis_client.keys("session:*")
    for key in keys:
        data = await redis_client.hgetall(key)
        session_id = key.decode().split(":")[1] if isinstance(key, bytes) else key.split(":")[1]
        sessions.append({
            "id": session_id,
            "candidate": data.get(b"candidate", b"Unknown").decode() if isinstance(data.get(b"candidate"), bytes) else data.get("candidate", "Unknown"),
            "stack": data.get(b"stack", b"python").decode() if isinstance(data.get(b"stack"), bytes) else data.get("stack", "python"),
            "status": "active",
            "trust_score": float(data.get(b"trust_score", b"100").decode() if isinstance(data.get(b"trust_score"), bytes) else data.get("trust_score", "100"))
        })
    return {"sessions": sessions}

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
                # Trigger AI response
                context = InterviewContext.from_event(event)
                asyncio.create_task(
                    ai.stream_reply(
                        session_id=session_id,
                        ws_manager=ws_manager,
                        context=context
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
