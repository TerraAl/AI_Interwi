from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx
from openai import AsyncOpenAI

from anticheat import AntiCheatSnapshot
from websocket_manager import WebsocketManager
from schemas import InterviewEvent

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")


@dataclass
class InterviewContext:
    message: str
    code: str = ""
    telemetry: Dict[str, Any] | None = None

    @classmethod
    def from_event(cls, event: InterviewEvent) -> "InterviewContext":
        payload = event.payload or {}
        return cls(
            message=payload.get("message", ""),
            code=payload.get("code", ""),
            telemetry=payload.get("telemetry", {}),
        )


class AIInterviewer:
    def __init__(
        self,
        manager: Optional[WebsocketManager] = None,
        chat_logger: Optional[Callable[[str, str, str], Awaitable[None]]] = None,
    ) -> None:
        self.system_prompt = (
            open(PROMPT_PATH, "r", encoding="utf-8").read()
            if os.path.exists(PROMPT_PATH)
            else "You are a FAANG staff engineer conducting a rigorous coding interview."
        )
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.ollama_host = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.client = AsyncOpenAI(api_key=self.openai_key) if self.openai_key else None
        self.code_snapshots: Dict[str, str] = {}
        self.ws_manager = manager or WebsocketManager()
        self.chat_logger = chat_logger

    def cache_code_snapshot(self, session_id: str, code: str) -> None:
        self.code_snapshots[session_id] = code

    async def capture_judge_feedback(
        self, session_id: str, judge_result: Dict[str, Any], anticheat: AntiCheatSnapshot
    ) -> None:
        summary = {
            "type": "judge_feedback",
            "judge_result": judge_result,
            "anticheat": anticheat.__dict__,
            "code": self.code_snapshots.get(session_id, ""),
        }
        await self.ws_manager.broadcast(session_id, summary)

    async def stream_reply(
        self, session_id: str, ws_manager: WebsocketManager, context: InterviewContext
    ) -> None:
        code = self.code_snapshots.get(session_id, "")
        telemetry = context.telemetry or {}
        content = (
            f"Candidate message:\n{context.message}\n\n"
            f"Latest code:\n```{code}```\n\n"
            f"Telemetry:\n{json.dumps(telemetry)}"
        )

        if telemetry.get("flag_large_paste"):
            warning = "Заметил большую вставку кода. Это твоё решение или ты воспользовался помощью?"
            await ws_manager.broadcast(
                session_id,
                {"type": "chat:ai", "message": warning, "meta": {"severity": "warning"}},
            )
            if self.chat_logger:
                await self.chat_logger(session_id, "ai", warning)

        if self.client:
            await self._stream_openai(session_id, ws_manager, content)
        elif self.groq_key:
            await self._stream_groq(session_id, ws_manager, content)
        else:
            await self._stream_ollama(session_id, ws_manager, content)

    async def _stream_openai(
        self, session_id: str, ws_manager: WebsocketManager, content: str
    ) -> None:
        stream = await self.client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            stream=True,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": content},
            ],
        )

        await ws_manager.broadcast(
            session_id, {"type": "chat:ai_status", "status": "started"}
        )
        buffer = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                await ws_manager.broadcast(
                    session_id, {"type": "chat:ai", "message": delta, "stream": True}
                )
                buffer.append(delta)
        await ws_manager.broadcast(
            session_id, {"type": "chat:ai_status", "status": "completed"}
        )
        if self.chat_logger and buffer:
            await self.chat_logger(session_id, "ai", "".join(buffer))

    async def _stream_groq(
        self, session_id: str, ws_manager: WebsocketManager, content: str
    ) -> None:
        headers = {"Authorization": f"Bearer {self.groq_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": content},
                    ],
                    "stream": True,
                },
            ) as response:
                buffer = []
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        payload = json.loads(data)
                        delta = payload["choices"][0]["delta"].get("content", "")
                        if delta:
                            await ws_manager.broadcast(
                                session_id,
                                {"type": "chat:ai", "message": delta, "stream": True},
                            )
                            buffer.append(delta)
                if self.chat_logger and buffer:
                    await self.chat_logger(session_id, "ai", "".join(buffer))
    async def _stream_ollama(
        self, session_id: str, ws_manager: WebsocketManager, content: str
    ) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.ollama_host}/api/generate",
                json={"model": "llama3.1:70b", "prompt": f"{self.system_prompt}\n\n{content}"},
            ) as response:
                buffer = []
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    if payload.get("done"):
                        break
                    token = payload.get("response", "")
                    if token:
                        await ws_manager.broadcast(
                            session_id,
                            {"type": "chat:ai", "message": token, "stream": True},
                        )
                        buffer.append(token)
                if self.chat_logger and buffer:
                    await self.chat_logger(session_id, "ai", "".join(buffer))

