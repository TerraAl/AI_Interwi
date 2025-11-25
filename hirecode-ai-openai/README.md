# HireCode AI (GPT-4o)

HireCode AI — демонстрационная платформа техсобеседований с живым AI-интервьюером. Полностью русифицированный интерфейс, все ответы AI на русском языке. Архитектура полностью повторяет боевую систему: FastAPI + PostgreSQL + Redis + Docker runner + React 18 / Vite / Tailwind / shadcn UI.

## Быстрый старт

```bash
cd hirecode-ai-openai
cp backend/.env.example backend/.env
# вставьте ключи
echo "OPENAI_API_KEY=sk-your-token" >> backend/.env
echo "OPENAI_BASE_URL=https://llm.t1v.scibox.tech/v1" >> backend/.env
echo "OPENAI_MODEL=qwen3-32b-awq" >> backend/.env

docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend / docs: http://localhost:8000/docs

## Ключевые фичи

- Monaco IDE в браузере с запуском решений в Docker (Python, JS, Java, C++).
- Автотесты (видимые + скрытые) с таймингами и лимитами, radon/pylint для качества кода.
- Anti-cheat в реальном времени: вставка >300 символов, DevTools, переключение вкладок — всё влияет на уровень доверия.
- AI-интервьювер на едином OpenAI совместимом endpoint (стриминг через WebSocket, комментарии к действиям кандидата).
- Elo-адаптив выдачи задач, админка для загрузки новых сценариев, PDF отчёт с кодом/чатом/метриками.
- Один WebSocket-канал для IDE, anticheat и чата.

## Структура

```
backend/  # FastAPI, Docker runner, judge, AI, античит, адаптив
frontend/ # React 18 + Vite + Tailwind + shadcn/ui
docker-compose.yml
```

## Настройки AI

- Единственный клиент OpenAI совместимого API: `OPENAI_API_KEY`, `OPENAI_BASE_URL` (по умолчанию `https://llm.t1v.scibox.tech/v1`), `OPENAI_MODEL`.
- Все ответы AI-интервьюера строго на русском языке.
- Используется `client.chat.completions.create(..., stream=True)` и один и тот же модельный идентификатор во всём приложении.

Минимальный `.env`:

```
OPENAI_API_KEY=sk-your-token
OPENAI_BASE_URL=https://llm.t1v.scibox.tech/v1
OPENAI_MODEL=qwen3-32b-awq
```

## Admin / финальный отчёт

- `http://localhost:5173/admin` — загрузка задач, просмотр уровня доверия и статуса сессий.
- В панели кандидата можно одним кликом выгрузить PDF со всем ходом интервью.

Готово к записи демо и пилотным интервью. Подключайте задачи, брендируйте дизайн и заводите реальных кандидатов.

