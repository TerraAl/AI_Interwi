from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from runner import DockerRunner, SupportedLanguage

TASKS_DIR = Path(__file__).parent / "tasks"


@dataclass
class JudgeResult:
    task_id: str
    passed: bool
    visible_tests: List[Dict[str, Any]]
    hidden_tests_passed: int
    metrics: Dict[str, Any]


class SubmissionJudge:
    def __init__(self) -> None:
        self.runner = DockerRunner()

    async def evaluate(self, code: str, language: SupportedLanguage, task_id: str) -> Dict[str, Any]:
        task_file = TASKS_DIR / f"{task_id}.json"
        if not task_file.exists():
            raise FileNotFoundError(f"Task {task_id} not found")
        task_data = json.loads(task_file.read_text(encoding="utf-8"))
        visible = task_data["tests"]["visible"]
        hidden = task_data["tests"]["hidden"]

        all_passed = True
        visible_results = []
        hidden_passed = 0
        metrics = {"max_elapsed_ms": 0}

        for test in visible:
            result = await self.runner.run(code, language, test["input"])
            success = (
                result.stdout.strip() == test["output"].strip()
                and result.exit_code == 0
            )
            all_passed = all_passed and success
            metrics["max_elapsed_ms"] = max(metrics["max_elapsed_ms"], result.elapsed_ms)
            visible_results.append(
                {
                    "input": test["input"],
                    "expected": test["output"],
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "passed": success,
                    "elapsed_ms": result.elapsed_ms,
                }
            )

        for test in hidden:
            result = await self.runner.run(code, language, test["input"])
            success = result.stdout.strip() == test["output"].strip() and result.exit_code == 0
            if success:
                hidden_passed += 1
            metrics["max_elapsed_ms"] = max(metrics["max_elapsed_ms"], result.elapsed_ms)
            all_passed = all_passed and success

        return {
            "task_id": task_id,
            "passed": all_passed,
            "visible_tests": visible_results,
            "hidden_tests_passed": hidden_passed,
            "metrics": metrics,
        }

