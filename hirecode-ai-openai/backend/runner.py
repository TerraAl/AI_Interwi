from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

import docker
from docker.errors import ContainerError


class SupportedLanguage(str, Enum):
    python = "python"
    javascript = "javascript"
    java = "java"
    cpp = "cpp"


LANGUAGE_CONFIG = {
    SupportedLanguage.python: {
        "image": "python:3.12-slim",
        "extension": ".py",
        "command": "cd /workspace && python Main.py < input.txt",
    },
    SupportedLanguage.javascript: {
        "image": "node:22-alpine",
        "extension": ".js",
        "command": "cd /workspace && node Main.js < input.txt",
    },
    SupportedLanguage.java: {
        "image": "openjdk:21-slim",
        "extension": ".java",
        "command": "cd /workspace && javac Main.java && cat input.txt | java Main",
    },
    SupportedLanguage.cpp: {
        "image": "gcc:14",
        "extension": ".cpp",
        "command": "cd /workspace && g++ Main.cpp -O2 -std=c++20 && cat input.txt | ./a.out",
    },
}


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: float
    memory_bytes: int


class DockerRunner:
    def __init__(self) -> None:
        self.client = docker.from_env()

    async def run(
        self, code: str, language: SupportedLanguage, input_data: str = ""
    ) -> ExecutionResult:
        config = LANGUAGE_CONFIG[language]
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / f"Main{config['extension']}"
            file_path.write_text(code, encoding="utf-8")
            input_file = Path(tmpdir) / "input.txt"
            input_file.write_text(input_data, encoding="utf-8")

            binds = {tmpdir: {"bind": "/workspace", "mode": "rw"}}
            command = ["bash", "-lc", config["command"]]
            container_name = f"hirecode-runner-{uuid.uuid4()}"

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._run_container(container_name, config["image"], command, binds),
            )
            return result

    def _run_container(
        self,
        name: str,
        image: str,
        command: List[str],
        binds: Dict[str, dict],
    ) -> ExecutionResult:
        start = time.perf_counter()
        container = self.client.containers.run(
            image=image,
            command=command,
            name=name,
            working_dir="/workspace",
            remove=False,
            tty=False,
            stdin_open=True,
            mem_limit="512m",
            network_disabled=True,
            volumes=binds,
            detach=True,
        )

        stdout = ""
        stderr = ""
        exit_code = 0
        try:
            exit_code = container.wait()["StatusCode"]
            stdout = container.logs(stdout=True, stderr=False).decode()
            stderr = container.logs(stdout=False, stderr=True).decode()
        except ContainerError as exc:
            exit_code = exc.exit_status
            stdout = ""
            stderr = str(exc)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            try:
                container.remove(force=True)
            except Exception:
                pass

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            elapsed_ms=elapsed,
            memory_bytes=0,
        )


runner = DockerRunner()

