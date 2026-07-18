/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans:  ['"PingFang SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        serif: ['"Noto Serif SC"', '"Songti SC"', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
