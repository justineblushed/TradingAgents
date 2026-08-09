import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef7ff",
          100: "#d9edff",
          500: "#2f6fed",
          600: "#2557c4",
          700: "#1c439a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
