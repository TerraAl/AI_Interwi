import { FormEvent, useEffect, useState } from "react";
import { Button } from "../components/ui/button";

type SessionRow = {
  id: string;
  candidate: string;
  stack: string;
  status: string;
  trust_score: number;
};

export default function AdminPanel() {
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [form, setForm] = useState({
    id: "",
    title: "",
    description: "",
    stack: "python",
  });

  const fetchSessions = () =>
    fetch("/api/admin/sessions")
      .then((res) => res.json())
      .then((data) => setSessions(data.sessions));

  useEffect(() => {
    fetchSessions();
  }, []);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    fetch("/api/admin/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        difficulty: 1500,
        elo: 1500,
        follow_up: [],
        tests: { visible: [], hidden: [] },
      }),
    }).then(() => {
      setForm({ id: "", title: "", description: "", stack: "python" });
    });
  };

  return (
    <main className="min-h-screen bg-canvas text-white p-8 space-y-8">
      <section className="rounded-3xl border border-white/10 p-6">
        <h1 className="text-2xl font-semibold mb-4">Admin / Company Panel</h1>
        <form className="grid grid-cols-2 gap-4" onSubmit={handleSubmit}>
          {(["id", "title", "description"] as const).map((field) => (
            <input
              key={field}
              value={form[field]}
              placeholder={field}
              className="bg-white/5 rounded-2xl px-4 py-3"
              onChange={(event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))}
            />
          ))}
          <Button className="col-span-2">Создать задачу</Button>
        </form>
      </section>

      <section className="rounded-3xl border border-white/5 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Последние сессии</h2>
          <Button variant="ghost" size="sm" onClick={fetchSessions}>
            Обновить
          </Button>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="text-white/60 uppercase text-xs">
            <tr>
              <th className="py-2">ID</th>
              <th>Кандидат</th>
              <th>Стек</th>
              <th>Статус</th>
              <th>Trust Score</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((row) => (
              <tr key={row.id} className="border-t border-white/5">
                <td className="py-2">{row.id.slice(0, 6)}…</td>
                <td>{row.candidate}</td>
                <td>{row.stack}</td>
                <td>{row.status}</td>
                <td>{row.trust_score.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

