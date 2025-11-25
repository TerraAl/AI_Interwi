from __future__ import annotations

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession


class AntiCheatSystem:
    """Система анти-читинга для отслеживания подозрительной активности кандидатов."""

    def __init__(self) -> None:
        self.session_scores: Dict[int, float] = {}  # session_id -> trust_score

    async def process_event(
        self, session_id: int, data: Dict[str, Any], db: AsyncSession
    ) -> float:
        """
        Обрабатывает событие анти-читинга и возвращает обновленный trust_score.
        
        Args:
            session_id: ID сессии интервью
            data: Данные события (тип, описание, severity и т.д.)
            db: Асинхронная сессия базы данных
            
        Returns:
            Обновленный trust_score (0-100)
        """
        event_type = data.get("type", "")
        severity = data.get("severity", 0.0)
        
        # Инициализируем счет для сессии, если его еще нет
        if session_id not in self.session_scores:
            self.session_scores[session_id] = 100.0
        
        current_score = self.session_scores[session_id]
        
        # Уменьшаем trust_score в зависимости от severity события
        # severity обычно от 0.0 до 1.0
        penalty = severity * 10.0  # Максимальный штраф 10 баллов за событие
        new_score = max(0.0, current_score - penalty)
        
        self.session_scores[session_id] = new_score
        
        return new_score

    def get_trust_score(self, session_id: int) -> float:
        """Получить текущий trust_score для сессии."""
        return self.session_scores.get(session_id, 100.0)

    def reset_session(self, session_id: int) -> None:
        """Сбросить счет для сессии."""
        if session_id in self.session_scores:
            del self.session_scores[session_id]

