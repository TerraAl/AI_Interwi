import MonacoEditor from "@monaco-editor/react";
import { useMemo } from "react";
import { clsx } from "clsx";

type Props = {
  language: string;
  code: string;
  onChange: (code: string) => void;
  onRun: () => void;
  onSubmit: () => void;
  running: boolean;
  results?: {
    visible_tests: Array<{
      input: string;
      expected: string;
      stdout: string;
      passed: boolean;
      elapsed_ms: number;
    }>;
    metrics?: Record<string, number>;
  };
};

const LANGUAGE_MAP: Record<string, string> = {
  python: "python",
  javascript: "javascript",
  java: "java",
  cpp: "cpp",
};

export default function IDE({
  language,
  code,
  onChange,
  onRun,
  onSubmit,
  running,
  results,
}: Props) {
  const monacoLang = useMemo(
    () => LANGUAGE_MAP[language] ?? "python",
    [language],
  );

  return (
    <section className="flex flex-col h-full rounded-3xl bg-panel/80 backdrop-blur border border-white/5">
      <header className="flex items-center justify-between px-5 py-3 border-b border-white/5">
        <div>
          <p className="text-xs uppercase text-white/60">Browser IDE</p>
          <h2 className="text-xl font-semibold">Monaco + Docker Runner</h2>
        </div>
        <div className="flex gap-3">
          <button
            onClick={onRun}
            disabled={running}
            className="px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 transition disabled:opacity-50"
          >
            Запустить
          </button>
          <button
            onClick={onSubmit}
            disabled={running}
            className="px-4 py-2 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400 text-black font-semibold disabled:opacity-50"
          >
            Отправить
          </button>
        </div>
      </header>

      <div className="flex-1 min-h-[400px]">
        <MonacoEditor
          height="100%"
          language={monacoLang}
          theme="vs-dark"
          value={code}
          onChange={(value) => onChange(value ?? "")}
          options={{
            fontSize: 15,
            roundedSelection: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
          }}
        />
      </div>

      {results && (
        <div className="border-t border-white/5 px-5 py-4 space-y-3 text-sm">
          <p className="text-white/70 uppercase tracking-wider text-xs">
            Автотесты
          </p>
          {results.visible_tests.map((test, idx) => (
            <div
              key={idx}
              className={clsx(
                "rounded-2xl px-4 py-3 border transition",
                test.passed
                  ? "border-emerald-500/30 bg-emerald-500/5"
                  : "border-rose-500/30 bg-rose-500/5",
              )}
            >
              <div className="flex items-center justify-between font-semibold">
                <span>Тест #{idx + 1}</span>
                <span>{test.passed ? "✅" : "❌"}</span>
              </div>
              <p className="text-white/60 mt-2">stdout: {test.stdout.trim()}</p>
              <p className="text-white/40">
                expected: {test.expected.trim()}
              </p>
              <p className="text-white/40">
                elapsed: {test.elapsed_ms.toFixed(1)} ms
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

