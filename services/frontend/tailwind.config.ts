import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  // CSS-variable-driven theming. Components write `bg-surface-2 text-text-primary`;
  // the actual values come from `--surface-2` / `--text-primary` set in index.css,
  // which switch on the `data-theme` attribute on <html>.
  theme: {
    extend: {
      colors: {
        // ── Brand primary (full tonal scale) ────────────────────────────────
        cobalt: {
          50:  '#EFF6FF',
          100: '#DBEAFE',
          200: '#BFDBFE',
          300: '#93C5FD',
          400: '#60A5FA',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
          DEFAULT: '#2563EB',
          hover:   '#1D4ED8',
        },

        // ── Brand accents (kept as-is, used in gradient + highlights) ──────
        aqua: '#06B6D4',
        sky:  '#22D3EE',

        // ── Neutral raw colors (still available for one-off needs) ─────────
        ink:   '#0B1F3A',
        mist:  '#94A3B8',
        cloud: '#E2E8F0',
        paper: '#F4F8FF',

        // ── Semantic, theme-aware tokens (resolve via CSS vars) ────────────
        // These are what app code should reach for by default.
        surface: {
          1: 'var(--surface-1)',  // page background
          2: 'var(--surface-2)',  // card / panel
          3: 'var(--surface-3)',  // modal / popover / elevated
          inverse: 'var(--surface-inverse)',
        },
        text: {
          primary:   'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted:     'var(--text-muted)',
          inverse:   'var(--text-inverse)',
          onAccent:  'var(--text-on-accent)',
        },
        border: {
          DEFAULT: 'var(--border)',
          strong:  'var(--border-strong)',
        },

        // ── Semantic feedback ──────────────────────────────────────────────
        success: '#16A34A',
        warning: '#F59E0B',
        error:   '#EF4444',
        info:    '#6366F1',  // recolored from sky-500 to avoid collision with brand `sky`

        // ── Data-viz categorical (Okabe–Ito-derived, colorblind-safer) ────
        chart: {
          1: '#2563EB',  // cobalt
          2: '#06B6D4',  // aqua
          3: '#16A34A',  // green
          4: '#F59E0B',  // amber
          5: '#A855F7',  // violet
          6: '#EC4899',  // pink
          7: '#64748B',  // slate
          8: '#0F766E',  // teal
        },
      },

      borderColor: {
        DEFAULT: 'var(--border)',
      },

      ringColor: {
        focus: 'var(--focus)',
      },

      boxShadow: {
        // Tinted shadows on light; flatter, darker on dark.
        sm: '0 1px 2px 0 var(--shadow-color)',
        DEFAULT: '0 1px 3px 0 var(--shadow-color), 0 1px 2px -1px var(--shadow-color)',
        md: '0 4px 6px -1px var(--shadow-color), 0 2px 4px -2px var(--shadow-color)',
        lg: '0 10px 15px -3px var(--shadow-color), 0 4px 6px -4px var(--shadow-color)',
      },

      backgroundImage: {
        'cv-signature': 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
      },
    },
  },
  plugins: [],
} satisfies Config
