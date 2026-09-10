import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only convenience so the frontend can call relative /auth, /llm,
    // /health paths without CORS setup. Production routing is a separate
    // decision (reverse proxy / same-origin deploy).
    proxy: {
      '/auth': 'http://localhost:8000',
      '/llm': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
