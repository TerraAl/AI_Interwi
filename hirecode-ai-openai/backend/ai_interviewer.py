import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Callable, Awaitable, Any

from openai import OpenAI
from websocket_manager import WebsocketManager

PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.txt"


class InterviewContext:
    """Контекст интервью для AI."""
    
    @staticmethod
    def from_event(event) -> Dict:
        return {
            "message": event.payload.get("message", ""),
            "telemetry": event.payload.get("telemetry", {})
        }


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
        self.client = (
            OpenAI(api_key=self.openai_key, base_url=self.base_url)
            if self.openai_key
            else None
        )
        self.code_snapshots: Dict[str, str] = {}
        self.ws_manager = manager or WebsocketManager()
        self.chat_logger = chat_logger
        self.active_streams: Dict[str, bool] = {}  # session_id -> is_streaming

    def cache_code_snapshot(self, session_id: str, code: str) -> None:
        """Кэширует снимок кода для контекста."""
        self.code_snapshots[session_id] = code

    async def stream_reply(
        self, session_id: str, ws_manager: WebsocketManager, context: Dict
    ) -> None:
        """Потоковая отправка ответа AI."""
        code = self.code_snapshots.get(session_id, "")
        telemetry = context.get("telemetry", {})
        message = context.get("message", "")
        
        content = (
            f"Candidate message:\n{message}\n\n"
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
        """Потоковая отправка через OpenAI."""
        self.active_streams[session_id] = True
        await ws_manager.broadcast(
            session_id, {"type": "chat:ai_status", "status": "started"}
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": content},
        ]

        try:
            loop = asyncio.get_running_loop()
            stream = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=2000,
                ),
            )

            full_response = ""
            for chunk in stream:
                if not self.active_streams.get(session_id, False):
                    break
                if chunk.choices and chunk.choices[0].delta.content:
                    content_chunk = chunk.choices[0].delta.content
                    full_response += content_chunk
                    await ws_manager.broadcast(
                        session_id,
                        {
                            "type": "chat:ai",
                            "message": content_chunk,
                            "stream": True,
                        },
                    )

            if self.chat_logger:
                await self.chat_logger(session_id, "ai", full_response)

        except Exception as e:
            error_msg = f"Ошибка при генерации ответа: {str(e)}"
            await ws_manager.broadcast(
                session_id, {"type": "chat:ai", "message": error_msg}
            )
            if self.chat_logger:
                await self.chat_logger(session_id, "ai", error_msg)
        finally:
            self.active_streams[session_id] = False
            await ws_manager.broadcast(
                session_id, {"type": "chat:ai_status", "status": "finished"}
            )

    async def capture_judge_feedback(
        self, session_id: str, judge_result: Dict, anticheat: Any
    ) -> None:
        """Захватывает обратную связь от судьи и генерирует комментарий AI."""
        # Можно добавить логику для генерации комментария на основе результатов
        pass
