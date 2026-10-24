/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Deep navy + teal, refined for a production security console:
        // higher contrast text, a calmer surface, and a single confident
        // accent color instead of scattered brights.
        navy: { DEFAULT: "#0A1526", 2: "#0F1D33", 3: "#1B2C47", 4: "#28395A" },
        teal: { DEFAULT: "#0EA5A8", light: "#5EEAD4" },
        mint: "#10B981",
        danger: "#DC2626",
        amber: "#D97706",
        ink: "#0F172A",
        slate: "#64748B",
        line: "#E6EAF0",
        surface: "#F6F8FB",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06)",
        raised: "0 4px 10px rgba(15,23,42,.06), 0 2px 4px rgba(15,23,42,.04)",
        popover: "0 12px 32px rgba(15,23,42,.14), 0 2px 8px rgba(15,23,42,.08)",
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem",
      },
    },
  },
  plugins: [],
};
