import { FormEvent, useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Eye, FileText, Users, Plus, RefreshCw } from "lucide-react";

type SessionRow = {
  id: string;
  candidate: string;
  stack: string;
  status: string;
  trust_score: number;
  created_at?: string;
  task_title?: string;
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
      setSessions(data.sessions || []);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessions();
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
      case 'failed': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getTrustScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400';
    if (score >= 60) return 'text-yellow-400';
    return 'text-red-400';
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
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-white/60 uppercase text-xs border-b border-white/10">
              <tr>
                <th className="py-3 px-4">ID</th>
                <th className="py-3 px-4">Кандидат</th>
                <th className="py-3 px-4">Стек</th>
                <th className="py-3 px-4">Статус</th>
                <th className="py-3 px-4">Доверие</th>
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
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 rounded-full bg-white/10 text-xs uppercase">
                      {row.stack}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`capitalize ${getStatusColor(row.status)}`}>
                      {row.status === 'completed' ? 'Завершено' :
                       row.status === 'in_progress' ? 'В процессе' :
                       row.status === 'failed' ? 'Ошибка' : row.status}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`font-semibold ${getTrustScoreColor(row.trust_score)}`}>
                      {row.trust_score.toFixed(1)}%
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
                    >
                      <Eye size={14} />
                      Просмотр
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

