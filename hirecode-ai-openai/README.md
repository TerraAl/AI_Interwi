# HireCode AI (GPT-4o)

HireCode AI — демонстрационная платформа техсобеседований с живым AI-интервьюером. Архитектура полностью повторяет боевую систему: FastAPI + PostgreSQL + Redis + Docker runner + React 18 / Vite / Tailwind / shadcn UI.

## Быстрый старт

```bash
cd hirecode-ai-openai
cp backend/.env.example backend/.env
# вставьте ключ
echo "OPENAI_API_KEY=sk-..." >> backend/.env

docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend / docs: http://localhost:8000/docs

## Ключевые фичи

- Monaco IDE в браузере с запуском решений в Docker (Python, JS, Java, C++).
- Автотесты (видимые + скрытые) с таймингами и лимитами, radon/pylint для качества кода.
- Anti-cheat в реальном времени: paste >300 символов, DevTools, tab switch — всё едет в trust score.
- AI-интервьювер (GPT-4o → Ollama/Groq fallback), стриминг через WebSocket, комментарии к действиям кандидата.
- Elo-адаптив выдачи задач, админка для загрузки новых сценариев, PDF отчёт с кодом/чатом/метриками.
- Один WebSocket-канал для IDE, anticheat и чата.

## Структура

```
backend/  # FastAPI, Docker runner, judge, AI, античит, адаптив
frontend/ # React 18 + Vite + Tailwind + shadcn/ui
docker-compose.yml
```

## Настройки AI

- Основной режим: OpenAI GPT-4o (client.chat.completions.create stream=True).
- Fallback 1: Groq (llama3.1 70B).
- Fallback 2: Ollama (llama3.1:70b) — запускается отдельным контейнером, если нет ключей.

В `backend/.env` можно указать любые комбинации ключей — приоритет идёт сверху вниз.

## Admin / финальный отчёт

- `http://localhost:5173/admin` — загрузка задач, просмотр trust score и статуса.
- В панели кандидата можно одним кликом выгрузить PDF со всем ходом интервью.

Готово к записи демо и пилотным интервью. Подключайте задачи, брендируйте дизайн и заводите реальных кандидатов.

