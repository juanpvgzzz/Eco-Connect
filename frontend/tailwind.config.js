// Tailwind 3 se usa para utilidades de maquetación; los colores y fuentes
// salen de los tokens CSS del manual (src/styles/tokens.css).
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        eco: {
          forest: "var(--eco-forest)",
          green: "var(--eco-green)",
          leaf: "var(--eco-leaf)",
          teal: "var(--eco-teal)",
          yellow: "var(--eco-yellow)",
          orange: "var(--eco-orange)",
          charcoal: "var(--eco-charcoal)",
          background: "var(--eco-background)",
          bg: "var(--eco-background)",
          border: "var(--eco-border)",
          muted: "var(--eco-muted)",
        },
      },
      fontFamily: {
        heading: "var(--font-heading)",
        body: "var(--font-body)",
      },
    },
  },
  plugins: [],
};
