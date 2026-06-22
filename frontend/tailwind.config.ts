import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        court: {
          hard: "#4a90d9",
          clay: "#c0724a",
          grass: "#4a9e5c",
        },
      },
    },
  },
  plugins: [],
};

export default config;
