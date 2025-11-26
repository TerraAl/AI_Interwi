from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from schemas import AdminTaskCreate

TASKS_DIR = Path(__file__).parent / "tasks"


@dataclass
class TaskRecord:
    id: str
    stack: str
    difficulty: int
    elo: int
    data: Dict


class AdaptiveEngine:
    def __init__(self) -> None:
        self.tasks: Dict[str, TaskRecord] = {}
        self._load_tasks()

    def _load_tasks(self) -> None:
        for file in TASKS_DIR.glob("*.json"):
            data = json.loads(file.read_text(encoding="utf-8"))
            self.tasks[data["id"]] = TaskRecord(
                id=data["id"],
                stack=data.get("stack", "python"),
                difficulty=data.get("difficulty", 1500),
                elo=data.get("elo", 1500),
                data=data,
            )

    def pick_task(self, stack: str) -> Optional[Dict]:
        candidates = [task for task in self.tasks.values() if task.stack == stack]
        if not candidates:
            candidates = list(self.tasks.values())
        if not candidates:
            return None
        task = random.choice(candidates)
        return task.data

    def pick_task_by_min_difficulty(
        self,
        stack: str,
        min_difficulty: int,
        fallback_label: str = "middle",
    ) -> Optional[Dict]:
        """Return a task with at least the requested difficulty."""
        candidates: List[TaskRecord] = [
            task
            for task in self.tasks.values()
            if task.stack == stack and task.difficulty >= min_difficulty
        ]
        if not candidates:
            candidates = [
                task for task in self.tasks.values() if task.difficulty >= min_difficulty
            ]
        if not candidates:
            candidates = list(self.tasks.values())
        if not candidates:
            return None

        choice = random.choice(candidates)
        data = dict(choice.data)
        data.setdefault("difficulty_label", fallback_label.capitalize())
        return data

    def save_task(self, payload: AdminTaskCreate) -> Dict:
        data = payload.dict()
        file = TASKS_DIR / f"{payload.id}.json"
        file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.tasks[payload.id] = TaskRecord(
            id=payload.id,
            stack=payload.stack,
            difficulty=payload.difficulty,
            elo=payload.elo,
            data=data,
        )
        return data

