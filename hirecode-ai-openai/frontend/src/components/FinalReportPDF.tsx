import { Download } from "lucide-react";
import { useState } from "react";

interface FinalReportPDFProps {
  sessionId?: string;
  candidate?: string;
  taskTitle?: string;
  submittedCode?: string;
  language?: string;
  testResults?: {
    passed_tests: number;
    total_tests: number;
    execution_time?: number;
  };
  trust_score?: number;
  code_quality_score?: number;
  recommendations?: string[];
  chatHistory?: Array<{ role: string; content: string }>;
  isAdmin?: boolean;
  userEmail?: string;
  userPhone?: string;
  userLocation?: string;
  userPosition?: string;
}

export default function FinalReportPDF({
  sessionId,
  candidate = "Unknown",
  taskTitle = "Unknown Task",
  submittedCode = "",
  language = "python",
  testResults = { passed_tests: 0, total_tests: 0 },
  trust_score = 100,
  code_quality_score = 0,
  recommendations = [],
  chatHistory = [],
  isAdmin = false,
  userEmail,
  userPhone,
  userLocation,
  userPosition,
}: FinalReportPDFProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleDownloadPDF = async () => {
    if (!sessionId && !candidate) {
      alert("Недостаточно данных для создания отчета");
      return;
    }

    setIsLoading(true);
    try {
      console.log("[PDF] Starting PDF download with data:", {
        sessionId,
        candidate,
        taskTitle,
        testResults,
        trust_score,
      });

      const response = await fetch("/api/interview/report/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          candidate_name: candidate,
          task_title: taskTitle,
          submitted_code: submittedCode || "# No code submitted",
          language,
          test_results: testResults || { passed_tests: 0, total_tests: 0 },
          trust_score: trust_score || 100,
          code_quality_score: code_quality_score || 0,
          recommendations: recommendations || [],
          chat_history: chatHistory || [],
          email: userEmail,
          phone: userPhone,
          location: userLocation,
          position: userPosition,
        }),
      });

      console.log("[PDF] Response status:", response.status);
      console.log("[PDF] Response headers:", {
        contentType: response.headers.get("content-type"),
        contentDisposition: response.headers.get("content-disposition"),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("[PDF] Error response:", errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const blob = await response.blob();
      console.log("[PDF] Blob size:", blob.size, "bytes");

      if (blob.size === 0) {
        throw new Error("PDF файл пустой");
      }

      // Проверяем что это действительно PDF
      if (!blob.type.includes("pdf")) {
        console.warn("[PDF] Warning: Blob type is", blob.type, "expected application/pdf");
      }

      // Создаем URL и скачиваем файл
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `report_${candidate.replace(/\s+/g, "_")}_${new Date().getTime()}.pdf`;
      
      console.log("[PDF] Download link:", link.download);
      
      document.body.appendChild(link);
      link.click();
      
      // Очищаем
      setTimeout(() => {
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        console.log("[PDF] Download completed successfully");
      }, 100);
    } catch (error) {
      console.error("[PDF] Error downloading PDF:", error);
      const errorMessage = error instanceof Error ? error.message : "Неизвестная ошибка";
      alert(`Ошибка при создании отчета: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      onClick={handleDownloadPDF}
      disabled={isLoading}
      className="w-full px-4 py-3 rounded-2xl bg-gradient-to-r from-emerald-400 to-cyan-400 text-black font-semibold hover:from-emerald-500 hover:to-cyan-500 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      <Download size={20} />
      {isLoading ? "Генерируем отчет..." : "Скачать PDF отчет"}
    </button>
  );
}