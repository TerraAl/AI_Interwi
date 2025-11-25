import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "Inter", "sans-serif"],
      },
      colors: {
        canvas: "#0b0f19",
        panel: "#121826",
      },
    },
  },
  plugins: [],
} satisfies Config;

