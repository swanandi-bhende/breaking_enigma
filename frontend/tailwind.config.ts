import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg-base)",
        foreground: "var(--text-primary)",
        surface: "var(--surface)",
        'surface-hover': "var(--surface-hover)",
        border: "var(--border)",
        accent: "var(--accent)",
        'accent-dim': "var(--accent-dim)",
        warning: "var(--warning)",
        error: "var(--error)",
        success: "var(--success)",
        'text-primary': "var(--text-primary)",
        'text-secondary': "var(--text-secondary)",
        'text-code': "var(--text-code)",
        
        agent: {
          research: "var(--agent-research)",
          pm: "var(--agent-pm)",
          designer: "var(--agent-designer)",
          developer: "var(--agent-developer)",
          qa: "var(--agent-qa)",
          devops: "var(--agent-devops)",
          docs: "var(--agent-docs)",
        }
      },
      fontFamily: {
        sans: ['var(--font-syne)', 'sans-serif'],
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      }
    },
  },
  plugins: [],
};
export default config;
