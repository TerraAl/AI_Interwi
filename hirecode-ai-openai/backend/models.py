from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("InterviewSession", back_populates="user")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    difficulty = Column(String)  # easy, medium, hard
    category = Column(String)  # algorithms, data-structures, system-design
    language = Column(String)  # python, javascript, java, cpp
    initial_code = Column(Text)
    test_cases = Column(JSON)  # visible and hidden tests
    time_limit = Column(Float, default=5.0)  # seconds
    memory_limit = Column(Integer, default=256)  # MB
    elo_rating = Column(Float, default=1200)
    follow_up_questions = Column(JSON)  # AI follow-up questions
    created_at = Column(DateTime, default=datetime.utcnow)

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    current_task_id = Column(Integer, ForeignKey("tasks.id"))
    user_elo = Column(Float, default=1200)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    total_score = Column(Float, default=0)
    trust_score = Column(Float, default=100)  # Anti-cheat score
    final_report = Column(JSON, nullable=True)

    user = relationship("User", back_populates="sessions")
    task = relationship("Task")
    submissions = relationship("CodeSubmission", back_populates="session")
    chat_messages = relationship("ChatMessage", back_populates="session")
    anticheat_events = relationship("AntiCheatEvent", back_populates="session")

class CodeSubmission(Base):
    __tablename__ = "code_submissions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    code = Column(Text)
    language = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    execution_time = Column(Float, nullable=True)
    memory_used = Column(Float, nullable=True)
    passed_tests = Column(Integer, default=0)
    total_tests = Column(Integer, default=0)
    code_quality_score = Column(Float, nullable=True)
    test_results = Column(JSON)

    session = relationship("InterviewSession", back_populates="submissions")
    task = relationship("Task")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    sender = Column(String)  # 'ai' or 'user'
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_type = Column(String, default='text')  # text, code_change, anticheat_alert

    session = relationship("InterviewSession", back_populates="chat_messages")

class AntiCheatEvent(Base):
    __tablename__ = "anticheat_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    event_type = Column(String)  # paste, tab_switch, devtools, blur, etc.
    description = Column(String)
    severity = Column(Float, default=1.0)  # 0-1, how suspicious
    timestamp = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON)  # additional event data

    session = relationship("InterviewSession", back_populates="anticheat_events")
