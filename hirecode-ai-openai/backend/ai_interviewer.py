from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from openai import OpenAI

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
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://llm.t1v.scibox.tech/v1")
        self.model = os.getenv("OPENAI_MODEL", "qwen3-32b-awq")
        self.client = OpenAI(api_key=self.openai_key, base_url=self.base_url) if self.openai_key else None
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

        if not self.client:
            await ws_manager.broadcast(
                session_id,
                {
                    "type": "chat:ai",
                    "message": "LLM недоступен: не задан OPENAI_API_KEY.",
                },
            )
            return
        await self._stream_openai(session_id, ws_manager, content)

    async def _stream_openai(
        self, session_id: str, ws_manager: WebsocketManager, content: str
    ) -> None:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def produce() -> None:
            stream = self.client.chat.completions.create(
                model=self.model,
                stream=True,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
                top_p=float(os.getenv("OPENAI_TOP_P", "0.9")),
                max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "512")),
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    asyncio.run_coroutine_threadsafe(queue.put(delta), loop)
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        producer_task = asyncio.create_task(asyncio.to_thread(produce))

        await ws_manager.broadcast(session_id, {"type": "chat:ai_status", "status": "started"})
        buffer: list[str] = []
        while True:
            delta = await queue.get()
            if delta is None:
                break
            buffer.append(delta)
            await ws_manager.broadcast(session_id, {"type": "chat:ai", "message": delta, "stream": True})
        await producer_task
        await ws_manager.broadcast(session_id, {"type": "chat:ai_status", "status": "completed"})
        if self.chat_logger and buffer:
            await self.chat_logger(session_id, "ai", "".join(buffer))


