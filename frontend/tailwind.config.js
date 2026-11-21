/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#070b14", 900: "#0b1120", 800: "#111a2e", 700: "#1b2740" },
        accent: { DEFAULT: "#7c8cff", soft: "#a5b0ff", cyan: "#4fd1c5", amber: "#f6ad55", rose: "#f68098" },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: { glow: "0 0 0 1px rgba(124,140,255,0.25), 0 8px 30px rgba(79,70,229,0.15)" },
    },
  },
  plugins: [],
};
