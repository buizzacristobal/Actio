import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#07122A", 900: "#0B1B33", 800: "#13294B", 700: "#1F3A66", 600: "#35517F", 500: "#5B7299", 300: "#A9B6CC", 100: "#E4E9F2" },
        gold: { 600: "#80591A", 500: "#B8893B", 400: "#CDA35A", 200: "#EAD6AE", 100: "#F6EBD3" },
        paper: "#F8F6F1",
        line: "#E4DFD3",
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", '"Times New Roman"', "serif"],
        sans: ["ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,27,51,.06), 0 4px 16px rgba(11,27,51,.05)",
        lift: "0 10px 40px rgba(11,27,51,.18)",
      },
    },
  },
  plugins: [],
};
export default config;
