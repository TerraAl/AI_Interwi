import { createContext, ReactNode, useCallback, useEffect, useMemo, useState } from "react";

type AntiCheatContextValue = {
  trustScore: number;
  registerEvent: (type: string, payload?: Record<string, unknown>) => void;
};

export const AntiCheatContext = createContext<AntiCheatContextValue>({
  trustScore: 100,
  registerEvent: () => undefined,
});

type Props = {
  children: ReactNode;
  onEvent: (type: string, payload?: Record<string, unknown>) => void;
};

export default function AntiCheatProvider({ children, onEvent }: Props) {
  const [score, setScore] = useState(100);
  const registerEvent = useCallback(
    (type: string, payload?: Record<string, unknown>) => {
      onEvent(type, payload);
      setScore((current) => Math.max(0, current - (payload?.penalty as number | undefined ?? 0)));
    },
    [onEvent],
  );

  useEffect(() => {
    const handlePaste = (event: ClipboardEvent) => {
      const text = event.clipboardData?.getData("text") ?? "";
      onEvent("anticheat:paste", { chars: text.length, penalty: text.length > 300 ? 10 : 0 });
    };

    const handleVisibility = () => {
      if (document.hidden) {
        onEvent("anticheat:tab_blur", { penalty: 5 });
      }
    };

    const handleKey = (event: KeyboardEvent) => {
      if (event.code === "F12" || (event.ctrlKey && event.shiftKey && event.code === "KeyI")) {
        onEvent("anticheat:devtools", { penalty: 30 });
      }
    };

    window.addEventListener("paste", handlePaste);
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("keydown", handleKey);

    return () => {
      window.removeEventListener("paste", handlePaste);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("keydown", handleKey);
    };
  }, [onEvent]);

  const value = useMemo(() => ({ trustScore: score, registerEvent }), [score, registerEvent]);

  return <AntiCheatContext.Provider value={value}>{children}</AntiCheatContext.Provider>;
}

