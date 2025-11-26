from __future__ import annotations

import asyncio
import io
import json
import os
import tarfile
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

            archive = self._build_workspace_archive(
                {
                    f"Main{config['extension']}": file_path,
                    "input.txt": input_file,
                }
            )

            command = ["bash", "-lc", "cd /workspace && " + config["command"]]
            container_name = f"hirecode-runner-{uuid.uuid4()}"

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._run_container(
                    container_name,
                    config["image"],
                    command,
                    archive,
                ),
            )
            return result

    def _run_container(
        self,
        name: str,
        image: str,
        command: List[str],
        archive: bytes,
    ) -> ExecutionResult:
        start = time.perf_counter()
        container = self.client.containers.create(
            image=image,
            command=command,
            name=name,
            working_dir="/workspace",
            tty=False,
            stdin_open=False,
            mem_limit="512m",
            network_disabled=True,
        )

        try:
            container.put_archive("/", archive)
        except Exception:
            container.remove(force=True)
            raise

        container.start()

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


    def _build_workspace_archive(self, files: Dict[str, Path]) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            for arcname, path in files.items():
                data = path.read_bytes()
                info = tarfile.TarInfo(name=f"workspace/{arcname}")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        buffer.seek(0)
        return buffer.read()


runner = DockerRunner()

