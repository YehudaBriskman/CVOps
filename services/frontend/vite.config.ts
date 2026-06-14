import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // The API owns the /api/v1 prefix, so this is a pass-through (no rewrite) —
      // same as the nginx edge. /api/v1/* is forwarded verbatim to the API.
      '/api/v1': {
        target: 'http://localhost:8000',
      },
    },
  },
})
