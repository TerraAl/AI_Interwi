from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Any, List
from datetime import datetime


@dataclass
class AntiCheatSnapshot:
    session_id: str
    trust_score: float
    events: List[Dict]


class AntiCheatService:
    """Система анти-читинга для отслеживания подозрительной активности кандидатов."""

    def __init__(self) -> None:
        self.session_trust_scores: Dict[str, float] = defaultdict(lambda: 100.0)
        self.session_events: Dict[str, List[Dict]] = defaultdict(list)

    def bootstrap_session(self, session_id: str) -> None:
        """Инициализация сессии анти-читинга."""
        self.session_trust_scores[session_id] = 100.0
        self.session_events[session_id] = []

    def record_event(self, session_id: str, event: Any) -> None:
        """Запись события анти-читинга."""
        event_type = event.type if hasattr(event, 'type') else event.get("type", "unknown")
        payload = event.payload if hasattr(event, 'payload') else event.get("payload", {})
        
        # Используем penalty из события, если его нет - вычисляем severity
        penalty = payload.get("penalty", 0)
        
        # Если penalty не указан, вычисляем его по severity правилам
        if penalty == 0:
            severity = 0.1
            if event_type == "anticheat:paste":
                chars = payload.get("chars", 0)
                if chars > 300:
                    severity = min(1.0, (chars - 300) / 300.0)
            elif event_type in ["anticheat:devtools", "anticheat:tab_switch", "anticheat:tab_blur"]:
                severity = 0.3
            penalty = severity * 10
        
        self.session_events[session_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "description": payload.get("description", ""),
            "severity": penalty / 10.0,
            "metadata": payload
        })
        
        # Обновляем trust_score, вычитая penalty
        old_score = self.session_trust_scores[session_id]
        self.session_trust_scores[session_id] = max(0.0, self.session_trust_scores[session_id] - penalty)
        new_score = self.session_trust_scores[session_id]
        print(f"[ANTICHEAT] Event: {event_type}, Penalty: {penalty}, Score: {old_score} -> {new_score}")

    def snapshot(self, session_id: str) -> AntiCheatSnapshot:
        """Получение снимка состояния анти-читинга."""
        return AntiCheatSnapshot(
            session_id=session_id,
            trust_score=self.session_trust_scores[session_id],
            events=self.session_events[session_id]
        )

    def complete_session(self, session_id: str) -> None:
        """Завершение сессии анти-читинга."""
        self.session_trust_scores.pop(session_id, None)
        self.session_events.pop(session_id, None)


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

