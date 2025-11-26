import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Sparkles } from "lucide-react";
import IDE from "../components/IDE";
import AIChat from "../components/AIChat";
import FinalReportPDF from "../components/FinalReportPDF";
import AntiCheatProvider from "../components/AntiCheatProvider";
import { InterviewSocket } from "../lib/websocket";

type UserData = {
  name: string;
  email: string;
  phone: string;
  location: string;
  position: string;
  stack: string;
};

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

type Progress = {
  tasks_completed: number;
  total_tasks: number;
  deadline_utc?: string;
} | null;

type Scoring = {
  correctness: number;
  optimality: number;
  style: number;
  communication: number;
  speed: number;
  overall: number;
  letter: string;
} | null;

export default function Interview() {
  const navigate = useNavigate();
  const location = useLocation();
  
  const [userData, setUserData] = useState<UserData | null>(null);
  const [session, setSession] = useState<SessionStart | null>(null);
  const [code, setCode] = useState("# Начни решение прямо здесь");
  const [language, setLanguage] = useState("python");
  const [messages, setMessages] = useState<
    Array<{ id: string; role: "user" | "ai" | "system"; content: string }>
  >([]);
  const [results, setResults] = useState<any>(null);
  const [progress, setProgress] = useState<Progress>(null);
  const [scoring, setScoring] = useState<Scoring>(null);
  const [remainingSec, setRemainingSec] = useState<number | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [anticheat, setAntiCheat] = useState<Record<string, unknown>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [interviewFinished, setInterviewFinished] = useState(false);
  const socketRef = useRef<InterviewSocket>();

  // Require user data from navigation state; force login on fresh visit
  useEffect(() => {
    const stateData = (location.state as any)?.userData;
    if (stateData) {
      setUserData(stateData);
      setLanguage(stateData.stack);
    } else {
      navigate("/login");
    }
  }, [navigate, location.state]);

  const handleFinishInterview = useCallback(async () => {
    if (!session) return;
    try {
      console.log("[INTERVIEW] Finishing interview session:", session.session_id);
      const response = await fetch("/api/interview/finish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.session_id }),
      });
      if (response.ok) {
        setInterviewFinished(true);
        console.log("[INTERVIEW] Interview finished successfully");
      } else {
        console.error("[INTERVIEW] Failed to finish interview:", response.statusText);
      }
    } catch (error) {
      console.error("[INTERVIEW] Error finishing interview:", error);
    }
  }, [session]);

  useEffect(() => {
    if (!userData) return; // Wait for user data
    
    let cancelled = false;
    let unsubscribe: (() => void) | null = null;
    const setup = async () => {
      const response = await fetch("/api/interview/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          candidate_name: userData.name, 
          stack: language,
          email: userData.email,
          phone: userData.phone,
          location: userData.location,
          position: userData.position,
        }),
      });
      const data: SessionStart & { progress?: Progress } = await response.json();
      if (cancelled) return;
      setSession(data);
      setProgress(data.progress ?? null);
      if (data.progress?.deadline_utc) {
        const deadlineMs = Date.parse(data.progress.deadline_utc);
        const update = () => {
          const diff = Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000));
          setRemainingSec(diff);
        };
        update();
        const timer = setInterval(update, 1000);
        // store timer in closure
        (window as any).__hc_timer = timer;
      }
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
          const content = String(message.message);
          if (content.trim().length > 0) {
            setMessages((prev) => [
              ...prev,
              { id: crypto.randomUUID(), role: "ai", content: content.trim() },
            ]);
          }
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
      const t = (window as any).__hc_timer;
      if (t) clearInterval(t);
      socketRef.current?.close();
      socketRef.current = undefined;
    };
  }, [language, userData]);

  const sendEvent = useCallback((type: string, payload?: Record<string, unknown>) => {
    console.log(`[WS] Sending event: ${type}`, payload);
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
        setProgress(payload.progress ?? null);
        setScoring(payload.scoring ?? null);
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

  const finishedByTime = useMemo(() => remainingSec !== null && remainingSec <= 0, [remainingSec]);
  const finishedByTasks = useMemo(
    () => (progress?.tasks_completed ?? 0) >= (progress?.total_tasks ?? 5),
    [progress]
  );
  const isFinished = interviewFinished || finishedByTime || finishedByTasks;

  useEffect(() => {
    if (session && (finishedByTime || finishedByTasks) && !interviewFinished) {
      handleFinishInterview();
    }
  }, [session, finishedByTime, finishedByTasks, interviewFinished, handleFinishInterview]);

  const handleNewInterview = useCallback(async () => {
    try {
      if (session && !isFinished) {
        await fetch("/api/interview/finish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: session.session_id }),
        });
      }
    } catch (e) {
      console.warn("[INTERVIEW] Could not finish existing session before starting new one:", e);
    }
    try {
      const t = (window as any).__hc_timer;
      if (t) clearInterval(t);
      socketRef.current?.close();
    } catch {}
    localStorage.removeItem("userData");
    navigate("/login");
  }, [session, isFinished, navigate]);

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
      <main className="min-h-screen bg-canvas text-white px-6 py-8 space-y-8 flex flex-col">
        <header className="flex flex-wrap items-center gap-6">
          <div className="h-12 w-12 rounded-2xl bg-white/10 flex items-center justify-center">
            <Sparkles className="text-emerald-300" />
          </div>
          <div>
            <p className="text-sm uppercase text-white/60">HireCode AI</p>
            <h1 className="text-3xl font-semibold">Живое AI-собеседование</h1>
            {userData && (
              <p className="text-sm text-white/50 mt-1">
                Кандидат: <span className="text-white">{userData.name}</span>
                {userData.position && <span> • {userData.position}</span>}
              </p>
            )}
            {progress && (
              <div className="mt-3">
                <div className="text-xs text-white/60 mb-1">
                  Задача {Math.min(progress.tasks_completed + 1, progress.total_tasks)}/{progress.total_tasks}
                  {typeof remainingSec === 'number' && (
                    <span className="ml-3">Осталось: {`${Math.floor(remainingSec/60).toString().padStart(2,'0')}:${(remainingSec%60).toString().padStart(2,'0')}`}</span>
                  )}
                </div>
                <div className="h-2 rounded-full bg-white/10 w-64">
                  <div
                    className="h-2 rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400"
                    style={{ width: `${(progress.tasks_completed / progress.total_tasks) * 100}%` }}
                  />
                </div>
              </div>
            )}
          </div>
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            disabled={isFinished}
            className="ml-auto rounded-2xl bg-white/5 px-4 py-2 border border-white/10 disabled:opacity-50"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="java">Java</option>
            <option value="cpp">C++</option>
          </select>
          <div className="ml-auto flex gap-2 items-center">
            <button
              onClick={handleNewInterview}
              className="rounded-2xl px-6 py-2 bg-white/10 hover:bg-white/20 text-white font-semibold transition-colors"
            >
              Новое интервью
            </button>
            <button
              onClick={handleFinishInterview}
              disabled={isFinished}
              className="rounded-2xl px-6 py-2 bg-red-500/80 hover:bg-red-600 disabled:bg-gray-600 text-white font-semibold transition-colors"
            >
              {isFinished ? "✓ Интервью завершено" : "Завершить интервью"}
            </button>
          </div>
        </header>
        <div className="grid grid-cols-12 gap-6 flex-1 overflow-hidden">
          <div className="col-span-3 space-y-4 overflow-y-auto">
            <div className="rounded-3xl bg-panel/50 border border-white/5 p-5">
              <p className="text-xs uppercase text-white/50 mb-1">Уровень доверия</p>
              <p className="text-4xl font-semibold">
                {typeof anticheat.trust_score === "number" ? anticheat.trust_score.toFixed(0) : 100}%
              </p>
              <p className="text-white/60 text-sm mt-2">В реальном времени фиксируем все подозрительные события.</p>
            </div>
            <FinalReportPDF
              sessionId={session?.session_id}
              candidate={userData?.name || "Unknown"}
              taskTitle={session?.task.title || "Unknown Task"}
              submittedCode={code}
              language={language}
              testResults={results?.metrics ?? { passed_tests: 0, total_tests: 0 }}
              trust_score={typeof anticheat.trust_score === "number" ? anticheat.trust_score : 100}
              code_quality_score={results?.metrics?.code_quality_score ?? 0}
              recommendations={results?.recommendations ?? []}
              chatHistory={messages}
              userEmail={userData?.email}
              userPhone={userData?.phone}
              userLocation={userData?.location}
              userPosition={userData?.position}
            />
          </div>
          <div className="col-span-6 overflow-hidden">
            <IDE
              language={language}
              code={code}
              running={isRunning}
              onChange={setCode}
              onRun={handleRun}
              onSubmit={handleRun}
              results={results}
              finished={isFinished}
            />
            {scoring && (
              <div className="mt-4 rounded-2xl bg-white/5 border border-white/10 p-4 text-sm">
                <div className="flex items-center justify-between">
                  <span className="uppercase text-white/60">Итоговая оценка</span>
                  <span className="text-lg font-semibold">{scoring.overall.toFixed(1)} / 100 ({scoring.letter})</span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2 text-white/80">
                  <div>Правильность: {scoring.correctness.toFixed(1)}</div>
                  <div>Оптимальность: {scoring.optimality.toFixed(1)}</div>
                  <div>Стиль: {scoring.style.toFixed(1)}</div>
                  <div>Коммуникация: {scoring.communication.toFixed(1)}</div>
                  <div>Скорость: {scoring.speed.toFixed(1)}</div>
                </div>
              </div>
            )}
          </div>
          <div className="col-span-3 overflow-hidden">
            <AIChat messages={messages} onSend={handleSendChat} streaming={streaming} />
          </div>
        </div>
      </main>
    </AntiCheatProvider>
  );
}

