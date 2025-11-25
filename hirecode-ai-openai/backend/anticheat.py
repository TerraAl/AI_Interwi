from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List

from schemas import InterviewEvent


@dataclass
class AntiCheatSnapshot:
    trust_score: float
    events: List[dict]
    paste_chars: int
    tab_switches: int
    devtools: int


class AntiCheatService:
    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, int | float | List[dict]]] = {}

    def bootstrap_session(self, session_id: str) -> None:
        self._sessions[session_id] = {
            "score": 100.0,
            "paste_chars": 0,
            "tab_switches": 0,
            "devtools": 0,
            "events": [],
            "updated_at": time.time(),
        }

    def record_event(self, session_id: str, event: InterviewEvent) -> None:
        session = self._sessions.setdefault(session_id, {
            "score": 100.0,
            "paste_chars": 0,
            "tab_switches": 0,
            "devtools": 0,
            "events": [],
            "updated_at": time.time(),
        })
        session["events"].append(event.dict())

        if event.type == "anticheat:paste":
            chars = event.payload.get("chars", 0)
            session["paste_chars"] += chars
            if chars > 300:
                session["score"] -= 10
        elif event.type == "anticheat:tab_blur":
            session["tab_switches"] += 1
            session["score"] -= 5
        elif event.type == "anticheat:devtools":
            session["devtools"] += 1
            session["score"] -= 30

        session["score"] = max(0, session["score"])
        session["updated_at"] = time.time()

    def snapshot(self, session_id: str) -> AntiCheatSnapshot:
        data = self._sessions.get(session_id)
        if not data:
            return AntiCheatSnapshot(
                trust_score=100,
                events=[],
                paste_chars=0,
                tab_switches=0,
                devtools=0,
            )
        return AntiCheatSnapshot(
            trust_score=data["score"],
            events=data["events"][-25:],
            paste_chars=data["paste_chars"],
            tab_switches=data["tab_switches"],
            devtools=data["devtools"],
        )

    def complete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

