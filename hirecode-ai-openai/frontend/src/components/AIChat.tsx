import { useEffect, useRef } from "react";
import { clsx } from "clsx";

type Message = {
  id: string;
  role: "user" | "ai" | "system";
  content: string;
};

type Props = {
  messages: Message[];
  onSend: (message: string) => void;
  streaming?: boolean;
};

export default function AIChat({ messages, onSend, streaming }: Props) {
  const formRef = useRef<HTMLFormElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  return (
    <section className="flex flex-col h-full rounded-3xl bg-panel/70 border border-white/5 overflow-hidden">
      <header className="px-5 py-4 border-b border-white/5">
        <p className="text-xs uppercase text-emerald-300/70">AI-интервьювер</p>
        <h2 className="text-xl font-semibold">Qwen3-32B-AWQ live поток</h2>
      </header>

      <div ref={containerRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Группируем сообщения пользователя отдельно, а AI в один блок */}
        {messages.filter(msg => msg.role === "user").map((msg) => (
          <div
            key={msg.id}
            className="px-4 py-3 rounded-2xl text-sm whitespace-pre-line leading-relaxed bg-white text-black"
          >
            {msg.content}
          </div>
        ))}

        {/* Все сообщения AI в одном блоке */}
        {messages.some(msg => msg.role === "ai") && (
          <div className="px-4 py-3 rounded-2xl text-sm whitespace-pre-line leading-relaxed bg-sky-500/10 border border-sky-500/20">
            {messages
              .filter(msg => msg.role === "ai")
              .map(msg => msg.content)
              .join("")}
          </div>
        )}

        {/* Системные сообщения */}
        {messages.filter(msg => msg.role === "system").map((msg) => (
          <div
            key={msg.id}
            className="px-4 py-3 rounded-2xl text-sm whitespace-pre-line leading-relaxed bg-white/5 border border-white/10 text-white/60 text-xs uppercase"
          >
            {msg.content}
          </div>
        ))}

        {streaming && (
          <div className="animate-pulse text-white/60 text-sm">AI печатает…</div>
        )}
      </div>

      <form
        ref={formRef}
        className="border-t border-white/5 px-5 py-4 flex gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const form = formRef.current;
          if (!form) return;
          const formData = new FormData(form);
          const value = (formData.get("message") as string).trim();
          if (!value) return;
          onSend(value);
          form.reset();
        }}
      >
        <input
          name="message"
          placeholder="Сформулируй решение, сложность, trade-offs…"
          className="flex-1 rounded-2xl bg-white/10 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sky-500/50"
        />
        <button
          type="submit"
          className="px-4 py-3 rounded-2xl bg-white text-black font-semibold"
        >
          Отправить
        </button>
      </form>
    </section>
  );
}

