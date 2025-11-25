from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class InterviewInitRequest(BaseModel):
    candidate_name: str
    stack: str = Field(..., description="Preferred language stack")


class InterviewInitResponse(BaseModel):
    session_id: str
    task: Dict


class SubmissionRequest(BaseModel):
    session_id: str
    task_id: str
    code: str
    language: str


class SubmissionResponse(BaseModel):
    task_id: str
    passed: bool
    visible_tests: List[Dict]
    hidden_tests_passed: int
    metrics: Dict[str, float]
    code_quality: Dict | None = None


class InterviewEvent(BaseModel):
    type: str
    payload: Dict = Field(default_factory=dict)


class AdminTaskCreate(BaseModel):
    id: str
    stack: str
    difficulty: int
    elo: int
    title: str
    description: str
    follow_up: List[str]
    tests: Dict[str, List[Dict[str, str]]]


class AdminTaskResponse(BaseModel):
    task: Dict

