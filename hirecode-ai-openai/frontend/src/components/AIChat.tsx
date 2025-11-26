import { useEffect, useRef, useState } from "react";
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [textValue, setTextValue] = useState("");

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const textarea = e.target;
    setTextValue(textarea.value);
    // Автоматическое расширение textarea
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
  };

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

      <div ref={containerRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        {/* Выводим все сообщения в хронологическом порядке как диалог */}
        {messages.map((msg) => {
          if (msg.role === "system") {
            return (
              <div
                key={msg.id}
                className="px-4 py-3 rounded-2xl text-sm whitespace-pre-line leading-relaxed bg-white/5 border border-white/10 text-white/60 text-xs uppercase"
              >
                {msg.content}
              </div>
            );
          }
          
          if (msg.role === "user") {
            return (
              <div
                key={msg.id}
                className="flex justify-end"
              >
                <div className="px-4 py-3 rounded-2xl text-sm whitespace-pre-line leading-relaxed bg-white text-black max-w-[80%]">
                  {msg.content}
                </div>
              </div>
            );
          }
          
          if (msg.role === "ai") {
            return (
              <div
                key={msg.id}
                className="flex justify-start"
              >
                <div className="px-4 py-3 rounded-2xl text-sm leading-relaxed bg-sky-500/10 border border-sky-500/20 overflow-hidden break-words max-w-[80%]">
                  {msg.content}
                </div>
              </div>
            );
          }
        })}

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
          setTextValue("");
          if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
          }
          form.reset();
        }}
      >
        <textarea
          ref={textareaRef}
          name="message"
          value={textValue}
          onChange={handleTextChange}
          placeholder="Сформулируй решение, сложность, trade-offs…"
          className="flex-1 rounded-2xl bg-white/10 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sky-500/50 resize-none overflow-hidden max-h-[120px]"
          style={{ minHeight: "44px", height: "44px" }}
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

