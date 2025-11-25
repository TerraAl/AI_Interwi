import jsPDF from "jspdf";

type Props = {
  candidate: string;
  chat: Array<{ role: string; content: string }>;
  code: string;
  metrics: Record<string, unknown>;
  anticheat: Record<string, unknown>;
};

export default function FinalReportPDF({ candidate, chat, code, metrics, anticheat }: Props) {
  const handleExport = () => {
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    let y = 40;

    const write = (label: string, value: string) => {
      const lines = doc.splitTextToSize(`${label}: ${value}`, 520);
      lines.forEach((line) => {
        if (y > 760) {
          doc.addPage();
          y = 60;
        }
        doc.text(line, 40, y);
        y += 18;
      });
      y += 10;
    };

    doc.setFont("helvetica", "bold");
    doc.text(`HireCode AI — Отчёт по сессии`, 40, y);
    y += 30;
    doc.setFont("helvetica", "normal");
    write("Кандидат", candidate);
    write("Метрики", JSON.stringify(metrics));
    write("Анти-читинг", JSON.stringify(anticheat));
    write("Код", code.slice(0, 8000));
    write(
      "Чат",
      chat
        .map((message) => `${message.role.toUpperCase()}: ${message.content}`)
        .join(" | "),
    );

    doc.save(`hirecode-report-${candidate}.pdf`);
  };

  return (
    <button
      onClick={handleExport}
      className="w-full px-4 py-3 rounded-2xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-black font-semibold"
    >
      Скачать PDF отчёт
    </button>
  );
}

