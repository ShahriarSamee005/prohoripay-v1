import type { Config } from "tailwindcss";

/**
 * Blossom-Vermillion → Tailwind wiring.
 * Semantic names map onto the CSS variables defined in app/globals.css, so
 * flipping `.dark` on <html> re-resolves everything. Use these names in
 * components — never raw hex or Tailwind's default palette.
 */
const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Accent — magenta is the ONLY accent.
        brand: {
          DEFAULT: "var(--bv-brand)",
          deep: "var(--bv-brand-deep)",
          bright: "var(--bv-brand-bright)",
        },
        "on-brand": "var(--bv-on-brand)",

        // Surfaces
        background: "var(--bv-background)",
        surface: {
          DEFAULT: "var(--bv-surface)",
          high: "var(--bv-surface-high)",
          brand: "var(--bv-surface-brand)",
        },

        // Hairline / divider (border-default)
        default: "var(--bv-border)",

        // Text
        primary: "var(--bv-text-primary)",
        secondary: "var(--bv-text-secondary)",
        tertiary: "var(--bv-text-tertiary)",

        // Status — state only, never decoration.
        success: "var(--bv-success)",
        warning: "var(--bv-warning)",
        danger: "var(--bv-danger)",
        info: "var(--bv-info)",
      },
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      // The financial type scale (design.md §4). [size, { lineHeight, weight }].
      fontSize: {
        "display-lg": ["46px", { lineHeight: "1.04", fontWeight: "700" }],
        "display-md": ["38px", { lineHeight: "1.06", fontWeight: "700" }],
        "display-sm": ["30px", { lineHeight: "1.1", fontWeight: "700" }],
        "headline-lg": ["26px", { lineHeight: "1.2", fontWeight: "700" }],
        "headline-md": ["23px", { lineHeight: "1.2", fontWeight: "700" }],
        "headline-sm": ["20px", { lineHeight: "1.25", fontWeight: "600" }],
        "title-lg": ["18px", { lineHeight: "1.3", fontWeight: "600" }],
        "title-md": ["15px", { lineHeight: "1.35", fontWeight: "600" }],
        "title-sm": ["13px", { lineHeight: "1.4", fontWeight: "600" }],
        "body-lg": ["16px", { lineHeight: "1.5", fontWeight: "400" }],
        "body-md": ["14px", { lineHeight: "1.5", fontWeight: "400" }],
        "body-sm": ["12px", { lineHeight: "1.5", fontWeight: "400" }],
        "label-lg": ["15px", { lineHeight: "1.2", fontWeight: "600" }],
        "label-md": ["13px", { lineHeight: "1.2", fontWeight: "600" }],
        "label-sm": ["11px", { lineHeight: "1.2", fontWeight: "600" }],
      },
      borderRadius: {
        sm: "10px",
        md: "14px",
        lg: "20px",
        xl: "28px",
        pill: "9999px",
      },
      boxShadow: {
        card: "0 1px 3px 0 var(--bv-shadow-card), 0 10px 24px -14px var(--bv-shadow-card)",
        "brand-glow": "0 8px 30px -6px var(--bv-brand-glow)",
      },
      transitionDuration: {
        fast: "150ms",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
