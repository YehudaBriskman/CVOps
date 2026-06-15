/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
    css: false,
  },
  server: {
    // Accept the dev-VM Host header that the nginx edge forwards — Vite 5
    // otherwise rejects it with "Blocked request. This host is not allowed".
    host: true,
    allowedHosts: true,
    // The browser reaches the app through the edge on :80, so the HMR websocket
    // must connect back through :80, not directly to Vite's :5173.
    hmr: { clientPort: 80 },
    proxy: {
      // The API owns the /api/v1 prefix, so this is a pass-through (no rewrite) —
      // same as the nginx edge. /api/v1/* is forwarded verbatim to the API.
      '/api/v1': {
        target: 'http://localhost:8000',
      },
    },
  },
})
