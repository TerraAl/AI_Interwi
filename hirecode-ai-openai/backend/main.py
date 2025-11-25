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
import uvicorn

from models import Base, User, InterviewSession, Task
from schemas import (
    UserCreate, UserLogin, User as UserSchema,
    TaskCreate, Task as TaskSchema,
    InterviewSessionCreate, InterviewSession as SessionSchema,
    WSMessage, CodeUpdateMessage, AntiCheatAlertMessage, AIChatMessage
)
from ai_interviewer import AIInterviewer
from anticheat import AntiCheatSystem
from adaptive import AdaptiveEngine
from code_quality import CodeQualityAnalyzer
from websocket_manager import WebsocketManager

# Environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/hirecode")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# Database setup
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Redis setup
redis_client = redis.from_url(REDIS_URL)

# Managers
ws_manager = WebsocketManager()
ai_interviewer = AIInterviewer()
anticheat_system = AntiCheatSystem()
adaptive_selector = AdaptiveEngine()
code_analyzer = CodeQualityAnalyzer()

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    await websocket.accept()
    active_connections[session_id] = websocket

    try:
        # Send welcome message
        await ws_manager.send_to_session(session_id, {
            "type": "ai_message",
            "data": {
                "message": "Привет! Я — твой AI-интервьювер. Начнем собеседование. Расскажи, как ты планируешь решать задачу?",
                "streaming": False
            }
        })

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "code_update":
                await handle_code_update(session_id, message["data"], db)
            elif message["type"] == "anticheat_event":
                await handle_anticheat_event(session_id, message["data"], db)
            elif message["type"] == "chat_message":
                await handle_chat_message(session_id, message["data"], db)

    except WebSocketDisconnect:
        del active_connections[session_id]

async def handle_code_update(session_id: int, data: dict, db: AsyncSession):
    # Analyze code quality
    quality_score = await code_analyzer.analyze(data["code"], data["language"])

    # Run tests
    test_results = await run_code_tests(session_id, data, db)

    # Notify AI interviewer
    await ai_interviewer.on_code_change(session_id, data, test_results, quality_score, db)

    # Send results back
    await ws_manager.send_to_session(session_id, {
        "type": "code_results",
        "data": {
            "quality_score": quality_score,
            "test_results": test_results
        }
    })

async def handle_anticheat_event(session_id: int, data: dict, db: AsyncSession):
    # Process anticheat event
    trust_score = await anticheat_system.process_event(session_id, data, db)

    # Notify AI if suspicious
    if data.get("severity", 0) > 0.7:
        await ai_interviewer.on_anticheat_alert(session_id, data, db)

    # Send trust score update
    await ws_manager.send_to_session(session_id, {
        "type": "trust_score_update",
        "data": {"trust_score": trust_score}
    })

async def handle_chat_message(session_id: int, data: dict, db: AsyncSession):
    # Process user message
    await ai_interviewer.on_user_message(session_id, data["message"], db)

async def run_code_tests(session_id: int, code_data: dict, db: AsyncSession):
    # Placeholder for test execution
    # In real implementation, this would run code in Docker
    return {
        "passed": 2,
        "total": 3,
        "results": [
            {"test": "Basic case", "passed": True, "time": 0.001},
            {"test": "Edge case", "passed": True, "time": 0.002},
            {"test": "Large input", "passed": False, "time": 2.1, "error": "Time limit exceeded"}
        ]
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
