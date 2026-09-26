/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cyber: {
          dark: '#0a0d14',
          card: '#121824',
          border: '#1f293d',
          accent: '#3b82f6',
          danger: '#ef4444',
          warning: '#f59e0b',
          success: '#10b981',
          text: '#f1f5f9',
          muted: '#94a3b8',
        },
      },
    },
  },
  plugins: [],
}
