/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        rugby: {
          green: '#1a5c2e',
          gold: '#c4a84f',
          dark: '#1a1a2e',
        },
      },
    },
  },
  plugins: [],
};
