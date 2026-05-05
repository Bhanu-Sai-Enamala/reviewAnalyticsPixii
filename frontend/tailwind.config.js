/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202A",
        muted: "#5B6B76",
      },
      boxShadow: {
        panel: "0 12px 32px rgba(23, 32, 42, 0.08)",
      },
    },
  },
  plugins: [],
};
