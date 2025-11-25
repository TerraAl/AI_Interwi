export default function FinalReportPDF({ candidate, metrics, anticheat }) {
  const handleExport = () => {
    const report = `HireCode AI Отчет

Кандидат: ${candidate}
Дата: ${new Date().toLocaleDateString('ru-RU')}
Результаты тестов: ${metrics?.passed_tests || 0}/${metrics?.total_tests || 0}
Уровень доверия: ${anticheat?.trust_score || 100}%

Отчет готов!`;
    alert(report);
  };

  return (
    <button
      onClick={handleExport}
      className="w-full px-4 py-3 rounded-2xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-black font-semibold"
    >
      Скачать PDF отчет
    </button>
  );
}