/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // ColorHunt Light Palette (e1f0da, d4e7c5, bfd8af, 99bc85)
        'surface-sage': '#E1F0DA',
        'surface-container': '#D4E7C5',
        'surface-muted': '#BFD8AF',
        'accent-green': '#99BC85',
        'canvas-light': '#F8FAF7',
        'forest-primary': '#154212',
        'forest-container': '#2D5A27',
        'on-surface': '#0E1F12',
        'on-surface-variant': '#42493E',

        // Night / Neon Dark Mode Palette
        'dark-bg-base': '#0B110D',
        'dark-surface-1': '#121A14',
        'dark-surface-2': '#18241C',
        'neon-lime': '#A3E635',
        'pistachio-glow': '#BEF264',
        'emerald-accent': '#4ADE80',
        'on-dark': '#E1F0DA',
        'on-dark-muted': '#A3B899',

        // System feedback
        'error-alert': '#BA1A1A',
        'error-container': '#FFDAD6',
      },
      fontFamily: {
        title: ['"Hind Siliguri"', 'sans-serif'],
        body: ['"Noto Serif Bengali"', 'serif'],
        en: ['Inter', 'sans-serif'],
      },
      letterSpacing: {
        'en-tight': '-0.06em',
      },
      borderRadius: {
        'card': '1rem',
        'pill': '9999px',
      },
      boxShadow: {
        'subtle': '0 1px 4px rgba(0, 0, 0, 0.05)',
        'tonal': '0 4px 16px rgba(21, 66, 18, 0.06)',
        'neon': '0 0 20px rgba(163, 230, 53, 0.25)',
      }
    },
  },
  plugins: [],
};
