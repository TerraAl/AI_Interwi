import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from openai import AsyncOpenAI
from groq import Groq
import httpx
import aiohttp

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import InterviewSession, ChatMessage, Task, CodeSubmission
from websocket_manager import WebsocketManager

class AIInterviewer:
    def __init__(self):
        self.openai_client = None
        self.groq_client = None
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        # Initialize OpenAI if key available
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.openai_client = AsyncOpenAI(api_key=openai_key)

        # Initialize Groq as fallback
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            self.groq_client = Groq(api_key=groq_key)

        # Load system prompt
        with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

        self.ws_manager = WebsocketManager()
        self.active_streams: Dict[int, bool] = {}  # session_id -> is_streaming

    async def get_llm_client(self):
        """Get available LLM client in priority order: OpenAI -> Groq -> Ollama"""
        if self.openai_client:
            return "openai", self.openai_client
        elif self.groq_client:
            return "groq", self.groq_client
        else:
            return "ollama", None

    async def generate_response(
        self,
        session_id: int,
        user_message: str,
        context: Dict[str, Any],
        db: AsyncSession,
        stream: bool = True
    ) -> str:
        """Generate AI response with context awareness"""

        # Build conversation history
        history = await self._build_conversation_history(session_id, db)

        # Add current context
        current_code = context.get("current_code", "")
        test_results = context.get("test_results", {})
        quality_score = context.get("quality_score", 0)
        anticheat_events = context.get("anticheat_events", [])

        system_context = f"""
{self.system_prompt}

КОНТЕКСТ ТЕКУЩЕЙ СЕССИИ:
- Текущий код кандидата: {current_code[:1000]}{'...' if len(current_code) > 1000 else ''}
- Результаты тестов: {json.dumps(test_results, ensure_ascii=False)}
- Оценка качества кода: {quality_score}/10
- Подозрительные события: {len(anticheat_events)} обнаружено

ИСТОРИЯ БЕСЕДЫ:
{chr(10).join([f"{msg.sender.upper()}: {msg.message[:200]}{'...' if len(msg.message) > 200 else ''}" for msg in history[-5:]])}
"""

        messages = [
            {"role": "system", "content": system_context},
            *[{"role": "user" if msg.sender == "user" else "assistant", "content": msg.message}
              for msg in history[-10:]],  # Last 10 messages
            {"role": "user", "content": user_message}
        ]

        client_type, client = await self.get_llm_client()

        if client_type == "openai":
            return await self._call_openai(client, messages, session_id, stream)
        elif client_type == "groq":
            return await self._call_groq(client, messages, session_id, stream)
        else:
            return await self._call_ollama(messages, session_id, stream)

    async def _call_openai(self, client: AsyncOpenAI, messages: List[Dict], session_id: int, stream: bool) -> str:
        """Call OpenAI API with streaming"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for cost efficiency, can upgrade to gpt-4o
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                stream=stream
            )

            if stream:
                return await self._handle_openai_stream(response, session_id)
            else:
                return response.choices[0].message.content

        except Exception as e:
            print(f"OpenAI error: {e}")
            return "Извините, произошла ошибка при генерации ответа. Попробуем использовать другой сервис."

    async def _call_groq(self, client: Groq, messages: List[Dict], session_id: int, stream: bool) -> str:
        """Call Groq API as fallback"""
        try:
            response = await client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                stream=stream
            )

            if stream:
                return await self._handle_groq_stream(response, session_id)
            else:
                return response.choices[0].message.content

        except Exception as e:
            print(f"Groq error: {e}")
            return await self._call_ollama(messages, session_id, stream)

    async def _call_ollama(self, messages: List[Dict], session_id: int, stream: bool) -> str:
        """Call Ollama API as final fallback"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "llama3.1:70b",
                    "messages": messages,
                    "stream": stream,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2000
                    }
                }

                async with session.post(f"{self.ollama_url}/api/chat", json=payload) as response:
                    if response.status != 200:
                        return "Извините, все AI сервисы временно недоступны. Попробуйте позже."

                    if stream:
                        return await self._handle_ollama_stream(response, session_id)
                    else:
                        result = await response.json()
                        return result.get("message", {}).get("content", "Ошибка генерации ответа")

        except Exception as e:
            print(f"Ollama error: {e}")
            return "Произошла ошибка при подключении к AI сервису. Проверьте подключение."

    async def _handle_openai_stream(self, response, session_id: int) -> str:
        """Handle OpenAI streaming response"""
        self.active_streams[session_id] = True
        full_response = ""

        try:
            async for chunk in response:
                if not self.active_streams.get(session_id, False):
                    break

                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content

                    # Send chunk to frontend
                    await self.ws_manager.send_to_session(session_id, {
                        "type": "ai_message_chunk",
                        "data": {
                            "chunk": content,
                            "finished": False
                        }
                    })

            # Send completion
            await self.ws_manager.send_to_session(session_id, {
                "type": "ai_message_chunk",
                "data": {
                    "chunk": "",
                    "finished": True
                }
            })

        finally:
            self.active_streams[session_id] = False

        return full_response

    async def _handle_groq_stream(self, response, session_id: int) -> str:
        """Handle Groq streaming response"""
        self.active_streams[session_id] = True
        full_response = ""

        try:
            async for chunk in response:
                if not self.active_streams.get(session_id, False):
                    break

                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content

                    await self.ws_manager.send_to_session(session_id, {
                        "type": "ai_message_chunk",
                        "data": {
                            "chunk": content,
                            "finished": False
                        }
                    })

            await self.ws_manager.send_to_session(session_id, {
                "type": "ai_message_chunk",
                "data": {
                    "chunk": "",
                    "finished": True
                }
            })

        finally:
            self.active_streams[session_id] = False

        return full_response

    async def _handle_ollama_stream(self, response, session_id: int) -> str:
        """Handle Ollama streaming response"""
        self.active_streams[session_id] = True
        full_response = ""

        try:
            async for line in response.content:
                if not self.active_streams.get(session_id, False):
                    break

                line = line.decode('utf-8').strip()
                if line:
                    try:
                        data = json.loads(line)
                        if data.get("done"):
                            break

                        content = data.get("message", {}).get("content", "")
                        if content:
                            full_response += content

                            await self.ws_manager.send_to_session(session_id, {
                                "type": "ai_message_chunk",
                                "data": {
                                    "chunk": content,
                                    "finished": False
                                }
                            })

                    except json.JSONDecodeError:
                        continue

            await self.ws_manager.send_to_session(session_id, {
                "type": "ai_message_chunk",
                "data": {
                    "chunk": "",
                    "finished": True
                }
            })

        finally:
            self.active_streams[session_id] = False

        return full_response

    async def _build_conversation_history(self, session_id: int, db: AsyncSession) -> List[ChatMessage]:
        """Build conversation history for context"""
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp)
        )
        return result.scalars().all()

    async def on_code_change(self, session_id: int, code_data: Dict, test_results: Dict, quality_score: float, db: AsyncSession):
        """Handle code changes and provide feedback"""
        context = {
            "current_code": code_data["code"],
            "test_results": test_results,
            "quality_score": quality_score,
            "anticheat_events": []
        }

        # Generate contextual message
        message = f"Вижу, что ты обновил код. Результаты тестов: {test_results.get('passed', 0)}/{test_results.get('total', 0)} пройдено. Оценка качества: {quality_score:.1f}/10. Что думаешь об этом решении?"

        await self.generate_response(session_id, message, context, db, stream=True)

    async def on_anticheat_alert(self, session_id: int, event_data: Dict, db: AsyncSession):
        """Handle anticheat alerts"""
        severity = event_data.get("severity", 0)
        event_type = event_data.get("event_type", "unknown")

        if severity > 0.7:
            messages = {
                "paste": "Заметил большую вставку кода. Это твое решение или ты воспользовался помощью?",
                "tab_switch": "Ты переключался между вкладками. Всё в порядке?",
                "devtools": "Открыты developer tools. Что-то не так с задачей?",
                "blur": "Окно потеряло фокус. Отвлекся на что-то другое?"
            }

            message = messages.get(event_type, "Заметил подозрительную активность. Всё идет по плану?")

            context = {
                "anticheat_events": [event_data],
                "current_code": "",
                "test_results": {},
                "quality_score": 0
            }

            await self.generate_response(session_id, message, context, db, stream=True)

    async def on_user_message(self, session_id: int, message: str, db: AsyncSession):
        """Handle user chat messages"""
        # Save user message
        chat_msg = ChatMessage(
            session_id=session_id,
            sender="user",
            message=message,
            timestamp=datetime.utcnow()
        )
        db.add(chat_msg)
        await db.commit()

        # Get current context
        context = await self._get_current_context(session_id, db)

        # Generate AI response
        ai_response = await self.generate_response(session_id, message, context, db, stream=True)

        # Save AI response
        ai_msg = ChatMessage(
            session_id=session_id,
            sender="ai",
            message=ai_response,
            timestamp=datetime.utcnow()
        )
        db.add(ai_msg)
        await db.commit()

    async def _get_current_context(self, session_id: int, db: AsyncSession) -> Dict[str, Any]:
        """Get current session context"""
        # Get latest code submission
        result = await db.execute(
            select(CodeSubmission)
            .where(CodeSubmission.session_id == session_id)
            .order_by(CodeSubmission.submitted_at.desc())
            .limit(1)
        )
        latest_submission = result.scalar_one_or_none()

        # Get recent anticheat events
        result = await db.execute(
            select(AntiCheatEvent)
            .where(AntiCheatEvent.session_id == session_id)
            .order_by(AntiCheatEvent.timestamp.desc())
            .limit(5)
        )
        recent_events = result.scalars().all()

        return {
            "current_code": latest_submission.code if latest_submission else "",
            "test_results": latest_submission.test_results if latest_submission else {},
            "quality_score": latest_submission.code_quality_score if latest_submission else 0,
            "anticheat_events": [event.__dict__ for event in recent_events]
        }

    async def stop_streaming(self, session_id: int):
        """Stop active streaming for session"""
        self.active_streams[session_id] = False
