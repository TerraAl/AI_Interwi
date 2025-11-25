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
    let y = 60;
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();

    // Функция для добавления страницы при необходимости
    const checkPageBreak = (neededSpace: number = 60) => {
      if (y + neededSpace > pageHeight - 60) {
        doc.addPage();
        y = 60;
      }
    };

    // Заголовок
    doc.setFont("helvetica", "bold");
    doc.setFontSize(20);
    doc.text("HireCode AI", pageWidth / 2, y, { align: "center" });
    y += 20;

    doc.setFontSize(14);
    doc.text("Отчёт по техническому собеседованию", pageWidth / 2, y, { align: "center" });
    y += 30;

    // Разделитель
    doc.setLineWidth(1);
    doc.line(40, y, pageWidth - 40, y);
    y += 20;

    // Информация о кандидате
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.text("Информация о кандидате", 40, y);
    y += 15;

    doc.setFont("helvetica", "normal");
    doc.text(`Имя кандидата: ${candidate}`, 40, y);
    y += 12;
    doc.text(`Дата проведения: ${new Date().toLocaleDateString('ru-RU')}`, 40, y);
    y += 12;
    doc.text(`Время проведения: ${new Date().toLocaleTimeString('ru-RU')}`, 40, y);
    y += 20;

    // Метрики производительности
    checkPageBreak();
    doc.setFont("helvetica", "bold");
    doc.text("Метрики производительности", 40, y);
    y += 15;

    doc.setFont("helvetica", "normal");
    if (metrics && typeof metrics === 'object') {
      Object.entries(metrics).forEach(([key, value]) => {
        const displayKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        doc.text(`${displayKey}: ${String(value)}`, 40, y);
        y += 12;
        checkPageBreak();
      });
    }
    y += 10;

    // Анти-читинг анализ
    checkPageBreak();
    doc.setFont("helvetica", "bold");
    doc.text("Анализ анти-читинга", 40, y);
    y += 15;

    doc.setFont("helvetica", "normal");
    if (anticheat && typeof anticheat === 'object') {
      const trustScore = anticheat.trust_score;
      const events = anticheat.events || [];

      doc.text(`Уровень доверия: ${trustScore || 100}%`, 40, y);
      y += 12;

      if (Array.isArray(events) && events.length > 0) {
        doc.text(`Подозрительные события: ${events.length}`, 40, y);
        y += 12;
        events.slice(0, 5).forEach((event: any, idx: number) => {
          doc.text(`${idx + 1}. ${event.type || 'Неизвестное событие'}`, 50, y);
          y += 10;
          checkPageBreak();
        });
      } else {
        doc.text("Подозрительных событий не обнаружено", 40, y);
        y += 12;
      }
    }
    y += 10;

    // Решение кандидата
    checkPageBreak(200);
    doc.setFont("helvetica", "bold");
    doc.text("Предоставленное решение", 40, y);
    y += 15;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    const codeLines = doc.splitTextToSize(code.slice(0, 5000), 500);
    codeLines.forEach((line: string) => {
      if (y > pageHeight - 60) {
        doc.addPage();
        y = 60;
      }
      doc.text(line, 40, y);
      y += 10;
    });
    y += 20;

    // Чат с интервьюером
    checkPageBreak(100);
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.text("Диалог с AI-интервьюером", 40, y);
    y += 15;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);

    chat.forEach((message, index) => {
      checkPageBreak(40);
      const role = message.role === 'ai' ? 'AI-интервьюер' : 'Кандидат';
      doc.setFont("helvetica", "bold");
      doc.text(`${role}:`, 40, y);
      y += 12;

      doc.setFont("helvetica", "normal");
      const contentLines = doc.splitTextToSize(message.content, 480);
      contentLines.forEach((line: string) => {
        checkPageBreak();
        doc.text(line, 50, y);
        y += 10;
      });
      y += 8;
    });

    // Футер
    const totalPages = doc.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setFont("helvetica", "normal");
      doc.text(
        `Страница ${i} из ${totalPages} | HireCode AI — Автоматизированное техническое собеседование`,
        40,
        pageHeight - 30
      );
    }

    doc.save(`hirecode-report-${candidate}-${new Date().toISOString().split('T')[0]}.pdf`);
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

