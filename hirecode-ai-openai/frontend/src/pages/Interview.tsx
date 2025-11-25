import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import IDE from "../components/IDE";
import AIChat from "../components/AIChat";
import TaskDescription from "../components/TaskDescription";
import FinalReportPDF from "../components/FinalReportPDF";
import AntiCheatProvider from "../components/AntiCheatProvider";
import { InterviewSocket } from "../lib/websocket";

type SessionStart = {
  session_id: string;
  task: {
    id: string;
    title: string;
    description: string;
    follow_up: string[];
    stack: string;
  };
};

export default function Interview() {
  const [session, setSession] = useState<SessionStart | null>(null);
  const [code, setCode] = useState("# Начни решение прямо здесь");
  const [language, setLanguage] = useState("python");
  const [messages, setMessages] = useState<
    Array<{ id: string; role: "user" | "ai" | "system"; content: string }>
  >([]);
  const [results, setResults] = useState<any>(null);
  const [streaming, setStreaming] = useState(false);
  const [anticheat, setAntiCheat] = useState<Record<string, unknown>>({});
  const [isRunning, setIsRunning] = useState(false);
  const socketRef = useRef<InterviewSocket>();

  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | null = null;
    const setup = async () => {
      const response = await fetch("/api/interview/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_name: "Demo Candidate", stack: language }),
      });
      const data: SessionStart = await response.json();
      if (cancelled) return;
      setSession(data);
      setMessages([
        {
          id: crypto.randomUUID(),
          role: "system",
          content: `Задача: ${data.task.title}\n\n${data.task.description}`,
        },
        {
          id: crypto.randomUUID(),
          role: "ai",
          content: `Привет! Я твой интервьюер сегодня. Расскажи, как планируешь решать эту задачу?`,
        },
      ]);
      const socket = new InterviewSocket(data.session_id);
      socket.connect();
      socketRef.current = socket;
      unsubscribe = socket.onMessage((message) => {
        if (message.type === "chat:ai") {
          setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: "ai", content: String(message.message) },
          ]);
        } else if (message.type === "chat:ai_status") {
          setStreaming(message.status === "started");
        } else if (message.type === "anticheat") {
          setAntiCheat(message);
        }
      });
    };
    setup();
    return () => {
      cancelled = true;
      unsubscribe?.();
      socketRef.current?.close();
      socketRef.current = undefined;
    };
  }, [language]);

  const sendEvent = useCallback((type: string, payload?: Record<string, unknown>) => {
    socketRef.current?.send({ type, payload });
  }, []);

  const handleRun = useCallback(() => {
    if (!session) return;
    setIsRunning(true);
    fetch("/api/interview/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.session_id,
        task_id: session.task.id,
        code,
        language,
      }),
    })
      .then((res) => res.json())
      .then((payload) => {
        setResults(payload);
        sendEvent("code:update", { content: code });
      })
      .finally(() => {
        setIsRunning(false);
      });
  }, [session, code, language, sendEvent]);

  const handleSendChat = useCallback(
    (message: string) => {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: "user", content: message }]);
      sendEvent("chat:user", {
        message,
        code,
        telemetry: anticheat,
      });
    },
    [code, anticheat, sendEvent],
  );

  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center text-white text-lg">
        Запускаем Docker окружение и загружаем задачу…
      </div>
    );
  }

  return (
    <AntiCheatProvider
      onEvent={(type, payload) => {
        sendEvent(type, payload);
      }}
    >
      <main className="min-h-screen bg-canvas text-white px-6 py-8 space-y-8">
        <header className="flex flex-wrap items-center gap-6">
          <div className="h-12 w-12 rounded-2xl bg-white/10 flex items-center justify-center">
            <Sparkles className="text-emerald-300" />
          </div>
          <div>
            <p className="text-sm uppercase text-white/60">HireCode AI</p>
            <h1 className="text-3xl font-semibold">Живое AI-собеседование</h1>
          </div>
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            className="ml-auto rounded-2xl bg-white/5 px-4 py-2 border border-white/10"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="java">Java</option>
            <option value="cpp">C++</option>
          </select>
        </header>
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-3 space-y-4">
            <TaskDescription
              title={session.task.title}
              description={session.task.description}
              followUp={session.task.follow_up}
            />
            <div className="rounded-3xl bg-panel/50 border border-white/5 p-5">
              <p className="text-xs uppercase text-white/50 mb-1">Уровень доверия</p>
              <p className="text-4xl font-semibold">
                {typeof anticheat.trust_score === "number" ? anticheat.trust_score.toFixed(0) : 100}%
              </p>
              <p className="text-white/60 text-sm mt-2">В реальном времени фиксируем все подозрительные события.</p>
            </div>
            <FinalReportPDF
              candidate="Demo Candidate"
              chat={messages}
              code={code}
              metrics={results?.metrics ?? {}}
              anticheat={anticheat}
            />
          </div>
          <div className="col-span-5">
            <IDE
              language={language}
              code={code}
              running={isRunning}
              onChange={setCode}
              onRun={handleRun}
              onSubmit={handleRun}
              results={results}
            />
          </div>
          <div className="col-span-4">
            <AIChat messages={messages} onSend={handleSendChat} streaming={streaming} />
          </div>
        </div>
      </main>
    </AntiCheatProvider>
  );
}

