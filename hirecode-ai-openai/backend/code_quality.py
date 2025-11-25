from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict


class CodeQualityAnalyzer:
    """Анализатор качества кода с использованием radon и pylint."""

    def analyze(self, code: str, language: str) -> Dict:
        if language != "python":
            return {"quality": "n/a"}

        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "solution.py"
            file_path.write_text(code, encoding="utf-8")
            radon_cmd = ["radon", "cc", "-j", str(file_path)]
            pylint_cmd = ["pylint", str(file_path)]

            radon_output = subprocess.run(
                radon_cmd, capture_output=True, text=True, check=False
            )
            pylint_output = subprocess.run(
                pylint_cmd, capture_output=True, text=True, check=False
            )

            return {
                "radon": radon_output.stdout,
                "pylint": pylint_output.stdout,
                "pylint_score": self._extract_pylint_score(pylint_output.stdout),
            }

    @staticmethod
    def _extract_pylint_score(output: str) -> float:
        marker = "Your code has been rated at"
        for line in output.splitlines():
            if marker in line:
                try:
                    return float(line.split(marker)[1].split("/")[0])
                except Exception:
                    return 0.0
        return 0.0

