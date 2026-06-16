import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Dedicated test config (kept separate from vite.config.ts so the dev server
// setup stays untouched). jsdom + globals so tests read like Jest; MSW handles
// all network. A stable absolute API base makes axios requests resolve to a
// fixed origin that MSW handlers can match deterministically.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // A concrete origin so jsdom enables per-origin storage (localStorage) and
    // window.location is well-defined.
    environmentOptions: { jsdom: { url: 'http://localhost/' } },
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    env: {
      VITE_API_BASE_URL: 'http://localhost/api/v1',
    },
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/**/*.d.ts', 'src/main.tsx'],
    },
  },
})
