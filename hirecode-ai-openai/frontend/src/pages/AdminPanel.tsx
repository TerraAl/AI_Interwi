import { FormEvent, useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Eye, FileText, Users, Plus, RefreshCw, Download } from "lucide-react";

type SessionRow = {
  id: string;
  candidate: string;
  stack: string;
  status: string;
  trust_score: number | string;
  created_at?: string;
  task_title?: string;
  email?: string;
  phone?: string;
  location?: string;
  position?: string;
  tasks_completed?: number;
  total_tasks?: number;
  deadline_utc?: string;
  latest_score?: string;
  letter_grade?: string;
};
type TaskForm = {
  id: string;
  title: string;
  description: string;
  stack: string;
};

export default function AdminPanel() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [form, setForm] = useState<TaskForm>({
    id: "",
    title: "",
    description: "",
    stack: "python",
  });
  const [loading, setLoading] = useState(false);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin/sessions");
      const data = await res.json();
      console.log("[ADMIN-FETCH] Received sessions:", data);
      
      // Дедупликация по candidate имени - показываем только последнюю сессию каждого кандидата
      const sessionsData = data.sessions || [];
      console.log("[ADMIN-FETCH] Sessions count before dedup:", sessionsData.length);
      
      // Sort sessions by created_at (newer first) to ensure we pick the latest
      const sortedSessions = [...sessionsData].sort((a, b) => {
        const aTime = new Date(a.created_at || 0).getTime();
        const bTime = new Date(b.created_at || 0).getTime();
        return bTime - aTime; // Descending order (newest first)
      });
      
      // Use a Map to keep only the first (latest) occurrence of each candidate
      const sessionMap = new Map<string, SessionRow>();
      
      for (const session of sortedSessions) {
        const candidate = session.candidate;
        if (!sessionMap.has(candidate)) {
          sessionMap.set(candidate, session);
          console.log("[ADMIN-FETCH] Keeping latest session for:", candidate, "ID:", session.id, "created_at:", session.created_at);
        }
      }
      
      const uniqueSessions = Array.from(sessionMap.values());
      console.log("[ADMIN-FETCH] Unique sessions count:", uniqueSessions.length);
      setSessions(uniqueSessions);
    } catch (error) {
      console.error("[ADMIN-FETCH] Failed to fetch sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
    // Обновляем данные сессий каждые 3 секунды для получения актуальной информации о trust_score
    const interval = setInterval(() => {
      fetchSessions();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    try {
      await fetch("/api/admin/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          difficulty: 1500,
          elo: 1500,
          follow_up: [],
          tests: { visible: [], hidden: [] },
        }),
      });
      setForm({ id: "", title: "", description: "", stack: "python" });
      // Можно добавить уведомление об успехе
    } catch (error) {
      console.error("Failed to create task:", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed': return 'text-green-400';
      case 'in_progress': return 'text-yellow-400';
      case 'active': return 'text-blue-400';
      case 'failed': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getTrustScoreColor = (score: number | string) => {
    const numScore = typeof score === 'number' ? score : parseFloat(String(score) || '0');
    if (numScore >= 80) return 'text-green-400';
    if (numScore >= 60) return 'text-yellow-400';
    return 'text-red-400';
  };

  const formatRemaining = (deadline?: string) => {
    if (!deadline) return '-';
    const ms = Date.parse(deadline) - Date.now();
    if (!isFinite(ms) || ms <= 0) return '00:00';
    const s = Math.floor(ms / 1000);
    const mm = String(Math.floor(s / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  };

  const handleExportCSV = () => {
    const headers = [
      'id','candidate','stack','status','trust_score','tasks_completed','total_tasks','deadline_utc','latest_score','letter_grade','created_at','task_title','email','phone','location','position'
    ];
    const rows = sessions.map(s => [
      s.id,
      s.candidate,
      s.stack,
      s.status,
      typeof s.trust_score === 'number' ? s.trust_score.toFixed(1) : String(s.trust_score || ''),
      String(s.tasks_completed ?? ''),
      String(s.total_tasks ?? ''),
      s.deadline_utc ?? '',
      s.latest_score ?? '',
      s.letter_grade ?? '',
      s.created_at ?? '',
      s.task_title ?? '',
      s.email ?? '',
      s.phone ?? '',
      s.location ?? '',
      s.position ?? '',
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(x => `"${String(x).replace(/"/g,'""')}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `hirecode_sessions_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }, 50);
  };

  const handleDownloadReport = async (session: SessionRow) => {
    try {
      console.log("[ADMIN] Downloading report for session:", session);

      // Fetch detailed session data including test results
      const detailRes = await fetch(`/api/admin/sessions/${session.id}`);
      if (!detailRes.ok) {
        throw new Error(`Failed to fetch session details: ${detailRes.statusText}`);
      }
      const sessionDetails = await detailRes.json();
      console.log("[ADMIN] Session details:", sessionDetails);

      const response = await fetch("/api/interview/report/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.id,
          candidate_name: session.candidate,
          task_title: sessionDetails.task_title || session.task_title || "Unknown Task",
          submitted_code: "# Code from session (full code not available in admin view)",
          language: session.stack || "python",
          test_results: sessionDetails.test_results || { passed_tests: 0, total_tests: 0 },
          trust_score: typeof session.trust_score === 'number' 
            ? session.trust_score 
            : parseFloat(String(session.trust_score) || '100'),
          code_quality_score: sessionDetails.test_results?.code_quality || 0,
          recommendations: [],
          chat_history: [],
        }),
      });

      console.log("[ADMIN] Response status:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("[ADMIN] Error response:", errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const blob = await response.blob();
      console.log("[ADMIN] Blob size:", blob.size, "bytes");

      if (blob.size === 0) {
        throw new Error("PDF файл пустой");
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${session.candidate.replace(/\s+/g, "_")}_${new Date().getTime()}.pdf`;
      document.body.appendChild(a);
      a.click();
      
      setTimeout(() => {
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        console.log("[ADMIN] Report downloaded successfully");
      }, 100);
    } catch (error) {
      console.error("[ADMIN] Error downloading PDF:", error);
      const errorMessage = error instanceof Error ? error.message : "Неизвестная ошибка";
      alert(`Ошибка при создании отчета: ${errorMessage}`);
    }
  };

  return (
    <main className="min-h-screen bg-canvas text-white p-8 space-y-8">
      {/* Заголовок с статистикой */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="rounded-3xl bg-panel/50 border border-white/5 p-6">
          <div className="flex items-center gap-3 mb-2">
            <Users className="text-blue-400" size={24} />
            <h3 className="text-lg font-semibold">Всего сессий</h3>
          </div>
          <p className="text-3xl font-bold">{sessions.length}</p>
        </div>

        <div className="rounded-3xl bg-panel/50 border border-white/5 p-6">
          <div className="flex items-center gap-3 mb-2">
            <FileText className="text-green-400" size={24} />
            <h3 className="text-lg font-semibold">Завершено</h3>
          </div>
          <p className="text-3xl font-bold">
            {sessions.filter(s => s.status === 'completed').length}
          </p>
        </div>

        <div className="rounded-3xl bg-panel/50 border border-white/5 p-6">
          <div className="flex items-center gap-3 mb-2">
            <RefreshCw className="text-yellow-400" size={24} />
            <h3 className="text-lg font-semibold">В процессе</h3>
          </div>
          <p className="text-3xl font-bold">
            {sessions.filter(s => s.status === 'in_progress').length}
          </p>
        </div>
      </div>

      {/* Создание новой задачи */}
      <section className="rounded-3xl border border-white/10 p-6">
        <div className="flex items-center gap-3 mb-6">
          <Plus className="text-emerald-400" size={24} />
          <h1 className="text-2xl font-semibold">Создание новой задачи</h1>
        </div>

        <form className="space-y-6" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                ID задачи
              </label>
              <input
                value={form.id}
                placeholder="two_sum"
                className="w-full bg-white/5 rounded-2xl px-4 py-3 border border-white/10 focus:border-emerald-400 focus:outline-none transition-colors"
                onChange={(event) => setForm((prev) => ({ ...prev, id: event.target.value }))}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                Язык программирования
              </label>
              <select
                value={form.stack}
                onChange={(event) => setForm((prev) => ({ ...prev, stack: event.target.value }))}
                className="w-full bg-white/5 rounded-2xl px-4 py-3 border border-white/10 focus:border-emerald-400 focus:outline-none transition-colors"
              >
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="java">Java</option>
                <option value="cpp">C++</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">
              Название задачи
            </label>
            <input
              value={form.title}
              placeholder="Две суммы"
              className="w-full bg-white/5 rounded-2xl px-4 py-3 border border-white/10 focus:border-emerald-400 focus:outline-none transition-colors"
              onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-white/80 mb-2">
              Описание задачи
            </label>
            <textarea
              value={form.description}
              placeholder="Верните индексы двух чисел, сумма которых равна заданному целевому значению."
              rows={4}
              className="w-full bg-white/5 rounded-2xl px-4 py-3 border border-white/10 focus:border-emerald-400 focus:outline-none transition-colors resize-none"
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              required
            />
          </div>

          <Button
            type="submit"
            className="w-full md:w-auto px-8 py-3 bg-gradient-to-r from-emerald-500 to-cyan-400 hover:from-emerald-600 hover:to-cyan-500 text-black font-semibold rounded-2xl transition-all duration-200"
            disabled={loading}
          >
            {loading ? "Создание..." : "Создать задачу"}
          </Button>
        </form>
      </section>

      {/* Список сессий */}
      <section className="rounded-3xl border border-white/5 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <FileText className="text-blue-400" size={24} />
            <h2 className="text-xl font-semibold">Сессии кандидатов</h2>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchSessions}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
              Обновить
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExportCSV}
              className="flex items-center gap-2"
            >
              <Download size={16} />
              Export CSV
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-white/60 uppercase text-xs border-b border-white/10">
              <tr>
                <th className="py-3 px-4">ID</th>
                <th className="py-3 px-4">Кандидат</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4">Телефон</th>
                <th className="py-3 px-4">Стек</th>
                <th className="py-3 px-4">Статус</th>
                <th className="py-3 px-4">Доверие</th>
                <th className="py-3 px-4">Прогресс</th>
                <th className="py-3 px-4">Осталось</th>
                <th className="py-3 px-4">Score</th>
                <th className="py-3 px-4">Grade</th>
                <th className="py-3 px-4">Действия</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((row) => (
                <tr key={row.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="py-3 px-4 font-mono text-xs">
                    {row.id.slice(0, 8)}…
                  </td>
                  <td className="py-3 px-4 font-medium">{row.candidate}</td>
                  <td className="py-3 px-4">{row.email || "-"}</td>
                  <td className="py-3 px-4">{row.phone || "-"}</td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 rounded-full bg-white/10 text-xs uppercase">
                      {row.stack}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`capitalize ${getStatusColor(row.status)}`}>
                      {row.status === 'completed' ? 'Завершено' :
                       row.status === 'in_progress' ? 'В процессе' :
                       row.status === 'failed' ? 'Ошибка' :
                       row.status === 'active' ? 'Активно' : row.status}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`font-semibold ${getTrustScoreColor(row.trust_score)}`}>
                      {typeof row.trust_score === 'number' 
                        ? row.trust_score.toFixed(1) 
                        : parseFloat(String(row.trust_score) || '0').toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {`${row.tasks_completed ?? 0}/${row.total_tasks ?? 5}`}
                  </td>
                  <td className="py-3 px-4">
                    {formatRemaining(row.deadline_utc)}
                  </td>
                  <td className="py-3 px-4">{row.latest_score ?? '-'}</td>
                  <td className="py-3 px-4">{row.letter_grade ?? '-'}</td>
                  <td className="py-3 px-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300"
                      onClick={() => handleDownloadReport(row)}
                    >
                      <Download size={14} />
                      Отчет
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {sessions.length === 0 && !loading && (
            <div className="text-center py-12 text-white/60">
              <FileText size={48} className="mx-auto mb-4 opacity-50" />
              <p>Сессий пока нет</p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

