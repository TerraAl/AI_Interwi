from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class User(UserBase):
    id: int
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Task schemas
class TaskBase(BaseModel):
    title: str
    description: str
    difficulty: str
    category: str
    language: str
    initial_code: str
    test_cases: Dict[str, Any]
    time_limit: float = 5.0
    memory_limit: int = 256
    elo_rating: float = 1200
    follow_up_questions: List[str] = []

class TaskCreate(TaskBase):
    pass

class Task(TaskBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Session schemas
class InterviewSessionBase(BaseModel):
    user_id: int
    current_task_id: Optional[int] = None
    user_elo: float = 1200

class InterviewSessionCreate(InterviewSessionBase):
    pass

class InterviewSession(InterviewSessionBase):
    id: int
    started_at: datetime
    ended_at: Optional[datetime]
    total_score: float
    trust_score: float
    final_report: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True

# Submission schemas
class CodeSubmissionBase(BaseModel):
    session_id: int
    task_id: int
    code: str
    language: str

class CodeSubmissionCreate(CodeSubmissionBase):
    pass

class CodeSubmission(CodeSubmissionBase):
    id: int
    submitted_at: datetime
    execution_time: Optional[float]
    memory_used: Optional[float]
    passed_tests: int
    total_tests: int
    code_quality_score: Optional[float]
    test_results: Dict[str, Any]

    class Config:
        from_attributes = True

# Chat schemas
class ChatMessageBase(BaseModel):
    session_id: int
    sender: str
    message: str
    message_type: str = "text"

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# Anti-cheat schemas
class AntiCheatEventBase(BaseModel):
    session_id: int
    event_type: str
    description: str
    severity: float = 1.0
    metadata: Dict[str, Any] = {}

class AntiCheatEventCreate(AntiCheatEventBase):
    pass

class AntiCheatEvent(AntiCheatEventBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# WebSocket message schemas
class WSMessage(BaseModel):
    type: str
    data: Dict[str, Any]

class CodeUpdateMessage(BaseModel):
    code: str
    language: str

class AntiCheatAlertMessage(BaseModel):
    event_type: str
    description: str
    severity: float

class AIChatMessage(BaseModel):
    message: str
    streaming: bool = False

# Report schemas
class SessionReport(BaseModel):
    session_id: int
    user_email: str
    total_score: float
    trust_score: float
    tasks_completed: int
    chat_messages: List[ChatMessage]
    anticheat_events: List[AntiCheatEvent]
    final_feedback: str


class AdminTaskCreate(BaseModel):
    id: str
    title: str
    description: str
    stack: str
    difficulty: int
    elo: int
    follow_up: List[str]
    tests: Dict[str, Any]

# Interview API schemas
class InterviewInitRequest(BaseModel):
    candidate_name: str
    stack: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    position: Optional[str] = None

class SessionStartResponse(BaseModel):
    session_id: str
    task: Dict[str, Any]

class SubmissionRequest(BaseModel):
    session_id: str
    code: str
    language: str
    task_id: str

class SubmissionResponse(BaseModel):
    passed: bool
    visible_tests: List[Dict[str, Any]]
    hidden_tests: List[Dict[str, Any]]
    code_quality: Dict[str, Any]
    metrics: Dict[str, Any]

class InterviewEvent(BaseModel):
    type: str
    payload: Dict[str, Any] = {}

class ReportGenerateRequest(BaseModel):
    session_id: Optional[str] = None
    candidate_name: str
    task_title: str
    submitted_code: str
    language: str
    test_results: Dict[str, Any]
    trust_score: float
    code_quality_score: float
    recommendations: List[str] = []
    chat_history: List[Dict[str, str]] = []
    # Optional contact fields from the pre-interview form
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    position: Optional[str] = None