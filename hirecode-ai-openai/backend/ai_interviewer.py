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
        import re
        
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

            # Удаляем все области <think>...</think> из полного ответа после завершения потока
            cleaned_response = re.sub(r'<think>[\s\S]*?<\/think>', '', full_response, flags=re.IGNORECASE).strip()
            
            # Отправляем чистый ответ (только один раз, после удаления думок)
            if cleaned_response:
                await ws_manager.broadcast(
                    session_id,
                    {
                        "type": "chat:ai",
                        "message": cleaned_response,
                        "stream": False,
                    },
                )

            if self.chat_logger:
                await self.chat_logger(session_id, "ai", cleaned_response)

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
        try:
            visible = judge_result.get("visible_tests", [])
            passed = sum(1 for t in visible if t.get("passed"))
            total = len(visible)
            hidden = judge_result.get("hidden_tests_passed", 0)
            ms = judge_result.get("metrics", {}).get("max_elapsed_ms", 0)
            q = judge_result.get("code_quality", {})
            pylint_score = q.get("pylint_score", 0)
            trust = getattr(anticheat, "trust_score", 100)

            summary = (
                f"Результаты: {passed}/{total} видимых, скрытых пройдено: {hidden}.\n"
                f"Макс. время: {ms:.1f} ms. Pylint: {pylint_score:.1f}. Trust: {trust:.1f}%."
            )

            follow_up = "Опиши временную и пространственную сложность решения и возможные узкие места."
            if total > 0 and passed == total and hidden >= 1:
                follow_up = "Все тесты пройдены. Можно ли упростить код и снизить асимптотику на худшем кейсе?"
            elif total > 0 and passed < total:
                follow_up = "Какие кейсы ломаются? Предложи исправление без роста сложности."
            if trust < 70:
                follow_up += " Также прокомментируй большие вставки и источники решения."

            await self.ws_manager.broadcast(
                session_id,
                {"type": "chat:ai", "message": summary + "\n\n" + follow_up},
            )
        except Exception as e:
            await self.ws_manager.broadcast(
                session_id,
                {"type": "chat:ai", "message": f"Не удалось сформировать фидбек: {e}"},
            )

    async def generate_followup_question(self, task_title: str) -> str:
        """Generate a follow-up question after a successful task."""
        prompt = (
            "Ты технический интервьюер. Кандидат только что успешно решил задачу "
            f"«{task_title}». Задай один ёмкий уточняющий вопрос, который проверяет "
            "понимание архитектурных компромиссов и подготовит кандидата к более сложному этапу. "
            "Ответ должен быть на русском языке и занимать 1-2 предложения."
        )
        result = await self._simple_completion(prompt, temperature=0.8, max_tokens=200)
        if result:
            return result
        return (
            f"Отличная работа с задачей «{task_title}»! Расскажи, как поведёт себя твоё решение, "
            "если увеличить размер входных данных в 10 раз и появятся ограничения по памяти?"
        )

    async def evaluate_followup_answer(
        self, candidate_answer: str, next_task_title: str
    ) -> str:
        """Generate a short evaluation of candidate answer and introduce next task."""
        prompt = (
            "Ты ведёшь интервью. Вот ответ кандидата на уточняющий вопрос:\n"
            f"```\n{candidate_answer}\n```\n"
            "Сформулируй короткий отзыв (2-3 предложения): отметь сильные стороны и что можно улучшить. "
            f"Затем в явном виде пригласи кандидата перейти к следующей задаче «{next_task_title}» уровня Middle. "
            "Пиши по-русски."
        )
        result = await self._simple_completion(prompt, temperature=0.7, max_tokens=250)
        if result:
            return result
        return (
            "Спасибо за развёрнутый ответ — видно, что ты понимаешь основные узкие места решения. "
            f"Давай перейдём к более сложной задаче уровня Middle: «{next_task_title}». Удачи!"
        )

    async def _simple_completion(
        self,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> Optional[str]:
        """Utility helper for single-turn completions."""
        if not self.client:
            return None
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                ),
            )
            if response.choices:
                content = getattr(response.choices[0].message, "content", None)
                if content:
                    return content.strip()
            return None
        except Exception as exc:
            print(f"[AI] simple completion failed: {exc}")
            return None