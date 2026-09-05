import type { Config } from "tailwindcss"

/*
 * Maps the semantic tokens in app/globals.css into utility classes, so engineers
 * write `bg-severity-critical-soft` rather than `bg-red-500/15 text-red-400`.
 * Direct palette escapes still compile, but review rejects them.
 */

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        "border-strong": "hsl(var(--border-strong))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          soft: "hsl(var(--primary-soft))",
          "soft-foreground": "hsl(var(--primary-soft-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
          soft: "hsl(var(--success-soft))",
          "soft-foreground": "hsl(var(--success-soft-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
          soft: "hsl(var(--warning-soft))",
          "soft-foreground": "hsl(var(--warning-soft-foreground))",
        },
        danger: {
          DEFAULT: "hsl(var(--danger))",
          foreground: "hsl(var(--danger-foreground))",
          soft: "hsl(var(--danger-soft))",
          "soft-foreground": "hsl(var(--danger-soft-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
          soft: "hsl(var(--info-soft))",
          "soft-foreground": "hsl(var(--info-soft-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        severity: {
          critical: {
            DEFAULT: "hsl(var(--severity-critical))",
            soft: "hsl(var(--severity-critical-soft))",
            "soft-foreground": "hsl(var(--severity-critical-soft-foreground))",
          },
          high: {
            DEFAULT: "hsl(var(--severity-high))",
            soft: "hsl(var(--severity-high-soft))",
            "soft-foreground": "hsl(var(--severity-high-soft-foreground))",
          },
          medium: {
            DEFAULT: "hsl(var(--severity-medium))",
            soft: "hsl(var(--severity-medium-soft))",
            "soft-foreground": "hsl(var(--severity-medium-soft-foreground))",
          },
          low: {
            DEFAULT: "hsl(var(--severity-low))",
            soft: "hsl(var(--severity-low-soft))",
            "soft-foreground": "hsl(var(--severity-low-soft-foreground))",
          },
        },
        run: {
          success: {
            DEFAULT: "hsl(var(--run-success))",
            soft: "hsl(var(--run-success-soft))",
            "soft-foreground": "hsl(var(--run-success-soft-foreground))",
          },
          running: {
            DEFAULT: "hsl(var(--run-running))",
            soft: "hsl(var(--run-running-soft))",
            "soft-foreground": "hsl(var(--run-running-soft-foreground))",
          },
          failed: {
            DEFAULT: "hsl(var(--run-failed))",
            soft: "hsl(var(--run-failed-soft))",
            "soft-foreground": "hsl(var(--run-failed-soft-foreground))",
          },
          queued: {
            DEFAULT: "hsl(var(--run-queued))",
            soft: "hsl(var(--run-queued-soft))",
            "soft-foreground": "hsl(var(--run-queued-soft-foreground))",
          },
        },
      },
      borderRadius: {
        lg: "var(--radius-lg)",
        md: "var(--radius)",
        sm: "var(--radius-sm)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      // Five-step scale — pinned. Do not add a sixth.
      fontSize: {
        caption: ["0.75rem", { lineHeight: "1rem" }],
        body: ["0.875rem", { lineHeight: "1.375rem" }],
        h2: ["1rem", { lineHeight: "1.5rem", fontWeight: "600" }],
        h1: ["1.25rem", { lineHeight: "1.75rem", fontWeight: "600" }],
        display: ["1.75rem", { lineHeight: "2.25rem", fontWeight: "700", letterSpacing: "-0.01em" }],
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        shimmer: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms cubic-bezier(0.2,0.8,0.2,1)",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
}

export default config
