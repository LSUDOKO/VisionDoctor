/** @type {import('tailwindcss').Config} */
// Colours are plain CSS vars (hex, themed in index.css), so opacity modifiers like bg-ink/10 are not available.
const v = (n) => `var(--${n})`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        page: v("page"), tint: v("tint"), inset: v("inset"), ink: v("ink"), body: v("body"), label: v("label"),
        hairline: v("hairline"), pencil: v("pencil"), yellow: v("yellow"), forest: v("forest"), danger: v("danger"),
        mint: v("mint"), teal: v("teal"), blush: v("blush"),
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "sans-serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"Roboto Mono"', "ui-monospace", "monospace"],
      },
      borderRadius: { btn: "6px", card: "12px", nav: "16px" },
    },
  },
  plugins: [],
};
