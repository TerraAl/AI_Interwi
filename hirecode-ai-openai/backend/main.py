import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional
from datetime import datetime
from io import BytesIO

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from urllib.parse import quote
import uvicorn

from models import Base, User, InterviewSession, Task
from schemas import (
    UserCreate, UserLogin, User as UserSchema,
    TaskCreate, Task as TaskSchema,
    InterviewSessionCreate, InterviewSession as SessionSchema,
    WSMessage, CodeUpdateMessage, AntiCheatAlertMessage, AIChatMessage,
    InterviewInitRequest, SessionStartResponse, SubmissionRequest, SubmissionResponse,
    InterviewEvent, AdminTaskCreate, ReportGenerateRequest
)
from ai_interviewer import AIInterviewer, InterviewContext
from anticheat import AntiCheatService
from adaptive import AdaptiveEngine
from code_quality import CodeQualityAnalyzer
from judge import SubmissionJudge
from report_generator import generate_report_pdf
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
    now = datetime.utcnow().isoformat()
    
    # Initialize empty test results
    empty_result = {
        "task_id": task["id"],
        "passed": False,
        "visible_tests": [],
        "hidden_tests_passed": 0,
        "metrics": {"max_elapsed_ms": 0},
        "code_quality": 0
    }
    
    await redis_client.hset(
        f"session:{session_id}",
        mapping={
            "candidate": payload.candidate_name,
            "stack": payload.stack,
            "task_id": task["id"],
            "task_title": task.get("title", ""),
            "trust_score": "100.0",
            "status": "active",
            "created_at": now,
            "latest_result": json.dumps(empty_result),
        },
    )
    print(f"[SESSION] Created session {session_id} with empty test results initialized")
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
    print(f"[SUBMIT] Starting evaluation for task_id={payload.task_id}, language={language}")
    
    try:
        judge_result = await judge.evaluate(payload.code, language, payload.task_id)
        print(f"[SUBMIT] Judge evaluation complete. Result keys: {list(judge_result.keys())}")
    except Exception as e:
        print(f"[SUBMIT] ERROR in judge evaluation: {e}")
        import traceback
        traceback.print_exc()
        # Return empty results on judge error
        judge_result = {
            "task_id": payload.task_id,
            "passed": False,
            "visible_tests": [],
            "hidden_tests_passed": 0,
            "metrics": {"max_elapsed_ms": 0},
        }
        print(f"[SUBMIT] Using fallback empty judge result due to error")
    
    judge_result["code_quality"] = code_quality_analyzer.analyze(payload.code, payload.language)
    anticheat = anticheat_service.snapshot(payload.session_id)
    
    # Log test results
    visible_tests = judge_result.get("visible_tests", [])
    passed_visible = sum(1 for t in visible_tests if t.get("passed", False))
    hidden_passed = judge_result.get("hidden_tests_passed", 0)
    print(f"[SUBMIT] Test Results: Visible {passed_visible}/{len(visible_tests)}, Hidden {hidden_passed}")
    print(f"[SUBMIT] Visible tests structure: {visible_tests[:1] if visible_tests else 'NO TESTS'}")
    print(f"[SUBMIT] Judge Result: {judge_result.get('passed')}, Code Quality: {judge_result.get('code_quality')}")
    print(f"[SUBMIT] Session ID: {payload.session_id}, Trust Score: {anticheat.trust_score}, Events: {len(anticheat.events)}")
    
    # Update Redis with latest results and trust_score
    redis_data = {
        "latest_result": json.dumps(judge_result),
        "trust_score": str(anticheat.trust_score)
    }
    await redis_client.hset(
        f"session:{payload.session_id}",
        mapping=redis_data,
    )
    print(f"[SUBMIT] Updated Redis for session {payload.session_id}")
    print(f"[SUBMIT] Redis keys set: {list(redis_data.keys())}")
    print(f"[SUBMIT] latest_result size: {len(redis_data['latest_result'])} bytes")
    print(f"[SUBMIT] Updated Redis trust_score to {anticheat.trust_score}")
    
    # Capture AI feedback
    asyncio.create_task(
        ai.capture_judge_feedback(payload.session_id, judge_result, anticheat)
    )
    
    # Update session in database
    session.total_score = judge_result.get("metrics", {}).get("max_elapsed_ms", 0)
    session.trust_score = anticheat.trust_score
    await db.commit()
    print(f"[SUBMIT] Updated DB trust_score to {anticheat.trust_score}")
    
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
    try:
        keys = await redis_client.keys("session:*")
        print(f"[ADMIN-API] Found {len(keys)} session keys in Redis")
        for key in keys:
            try:
                # Check if key is a hash
                key_type = await redis_client.type(key)
                if key_type != b"hash" and key_type != "hash":
                    continue
                    
                data = await redis_client.hgetall(key)
                session_id = key.decode().split(":")[1] if isinstance(key, bytes) else key.split(":")[1]
                
                def get_value(data, field, default):
                    val = data.get(field.encode() if isinstance(field, str) else field, default.encode() if isinstance(default, str) else default)
                    if isinstance(val, bytes):
                        return val.decode()
                    return val
                
                # Получаем статус из Redis или устанавливаем "active" по умолчанию
                status = get_value(data, "status", "active")
                
                # Безопасное преобразование trust_score
                trust_score_str = get_value(data, "trust_score", "100.0")
                try:
                    trust_score = float(trust_score_str)
                    if trust_score < 0 or trust_score > 100:
                        trust_score = 100.0
                except (ValueError, TypeError) as e:
                    print(f"[ADMIN-API] Error converting trust_score '{trust_score_str}' to float for session {session_id}: {e}")
                    trust_score = 100.0
                
                candidate = get_value(data, "candidate", "Unknown")
                task_title = get_value(data, "task_title", "")
                created_at = get_value(data, "created_at", "")
                
                sessions.append({
                    "id": session_id,
                    "candidate": candidate,
                    "stack": get_value(data, "stack", "python"),
                    "email": get_value(data, "email", ""),
                    "phone": get_value(data, "phone", ""),
                    "location": get_value(data, "location", ""),
                    "position": get_value(data, "position", ""),
                    "status": status,
                    "trust_score": trust_score,
                    "task_title": task_title,
                    "created_at": created_at
                })
                print(f"[ADMIN-API] Session {session_id}: candidate={candidate}, status={status}, trust_score={trust_score}, created_at={created_at}")
            except Exception as e:
                # Skip invalid keys
                print(f"[ADMIN-API] Error processing session key {key}: {e}")
                import traceback
                traceback.print_exc()
                continue
    except Exception as e:
        print(f"Error listing sessions: {e}")
    return {"sessions": sessions}

@app.get("/api/admin/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed session information including test results"""
    try:
        data = await redis_client.hgetall(f"session:{session_id}")
        print(f"[ADMIN-DETAIL] Redis keys found for session {session_id}: {list(data.keys())}")
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        def get_value(data, field, default):
            val = data.get(field.encode() if isinstance(field, str) else field, default.encode() if isinstance(default, str) else default)
            if isinstance(val, bytes):
                return val.decode()
            return val
        
        # Parse latest_result which contains judge result
        latest_result_json = get_value(data, "latest_result", "{}")
        print(f"[ADMIN-DETAIL] latest_result_json length: {len(latest_result_json)}")
        try:
            latest_result = json.loads(latest_result_json)
            print(f"[ADMIN-DETAIL] Parsed latest_result keys: {list(latest_result.keys())}")
        except json.JSONDecodeError as e:
            print(f"[ADMIN-DETAIL] Failed to parse latest_result: {e}")
            latest_result = {}
        
        print(f"[ADMIN-DETAIL] Session {session_id}: Found latest_result with {len(latest_result)} keys")
        
        result_dict = {
            "id": session_id,
            "candidate": get_value(data, "candidate", "Unknown"),
            "stack": get_value(data, "stack", "python"),
            "status": get_value(data, "status", "active"),
            "trust_score": float(get_value(data, "trust_score", "100.0")),
            "task_title": get_value(data, "task_title", ""),
            "created_at": get_value(data, "created_at", ""),
            "test_results": latest_result,  # Include actual test results
        }
        print(f"[ADMIN-DETAIL] Returning result with test_results keys: {list(result_dict['test_results'].keys())}")
        return result_dict
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ADMIN-DETAIL] Error getting session details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: str) -> None:
    await ws_manager.connect(session_id, websocket)
    try:
        await websocket.accept()
        await websocket.send_json({"type": "connected", "session_id": session_id})

        async for message in websocket.iter_text():
            data = json.loads(message)
            event = InterviewEvent(**data)
            print(f"[WS] Received event: {event.type}")
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
                print(f"[ANTICHEAT] Event: {event.type}, Trust Score Before: {snapshot.trust_score}")
                
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
                    mapping={"trust_score": str(round(snapshot.trust_score, 2))},
                )
                print(f"[ANTICHEAT] Saved trust_score: {snapshot.trust_score} to Redis")
                # Примечание: trust_score в БД обновляется при завершении интервью
                
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
        # Обновляем статус сессии при завершении
        final_trust_score = anticheat_service.session_trust_scores.get(session_id, 100.0)
        await redis_client.hset(
            f"session:{session_id}",
            mapping={
                "status": "completed",
                "trust_score": str(round(final_trust_score, 2)),
            },
        )


@app.post("/api/interview/finish")
async def finish_interview(request: dict):
    """Завершить интервью и установить статус 'completed'"""
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    try:
        # Update Redis session status to 'completed'
        await redis_client.hset(
            f"session:{session_id}",
            "status",
            "completed"
        )
        print(f"[FINISH] Interview session {session_id} marked as completed")
        
        return {"status": "ok", "message": "Interview finished"}
    except Exception as e:
        print(f"[FINISH] Error finishing interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/interview/report/pdf")
async def generate_pdf_report(request: ReportGenerateRequest):
    try:
        # -------------------------------
        # 1. Загрузить контактную инфу (Redis → request override)
        # -------------------------------
        test_results = dict(request.test_results or {})

        email = request.email
        phone = request.phone
        location = request.location
        position = request.position

        if request.session_id:
            try:
                data = await redis_client.hgetall(f"session:{request.session_id}")

                def get_val(key):
                    v = data.get(key.encode())
                    return v.decode() if isinstance(v, bytes) else v

                # Redis → только если не передано в запросе
                email = email or get_val("email")
                phone = phone or get_val("phone")
                location = location or get_val("location")
                position = position or get_val("position")

                print(f"[REPORT] Loaded contact info from Redis for session {request.session_id}")
            except Exception as e:
                print(f"[REPORT] Redis fetch failed: {e}")

        # -------------------------------
        # 2. Генерация PDF
        # -------------------------------
        pdf_buffer = generate_report_pdf(
            candidate_name=request.candidate_name,
            task_title=request.task_title,
            submitted_code=request.submitted_code,
            language=request.language,
            test_results=test_results,
            trust_score=request.trust_score,
            code_quality_score=request.code_quality_score,
            recommendations=request.recommendations,
            chat_history=request.chat_history,
            email=email,
            phone=phone,
            location=location,
            position=position,
        )

        print(f"[REPORT] Generated PDF report for {request.candidate_name}")

        # -------------------------------
        # 3. Корректная генерация имени файла
        # -------------------------------
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # ASCII fallback name — обязательно
        ascii_filename = f"report_{ts}.pdf"

        # UTF-8 filename
        utf8_filename = quote(f"report_{request.candidate_name}_{ts}.pdf")

        content_disp = (
            f'attachment; filename="{ascii_filename}"; '
            f"filename*=UTF-8''{utf8_filename}"
        )

        # -------------------------------
        # 4. Возврат PDF
        # -------------------------------
        pdf_bytes = pdf_buffer.getvalue()

        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": content_disp,
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except Exception as e:
        print(f"[ERROR] Failed to generate PDF report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
