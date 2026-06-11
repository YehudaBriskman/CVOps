import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cobalt:  { DEFAULT: '#2563EB', hover: '#1D4ED8' },
        aqua:    '#06B6D4',
        sky:     '#22D3EE',
        ink:     '#0B1F3A',
        mist:    '#94A3B8',
        cloud:   '#E2E8F0',
        paper:   '#F4F8FF',
        success: '#16A34A',
        warning: '#F59E0B',
        error:   '#EF4444',
        info:    '#0EA5E9',
      },
      backgroundImage: {
        'cv-signature': 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
      },
    },
  },
  plugins: [],
} satisfies Config
