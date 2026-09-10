import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Bind IPv4 explicitly: by default Vite listens on localhost, which
    // resolves to ::1 only on this Windows setup, leaving 127.0.0.1
    // unreachable and making the dev server look dead to IPv4-only clients.
    host: '127.0.0.1',

    // Dev-only convenience so the frontend can call relative /auth, /llm,
    // /characters, /health paths without CORS setup. Production routing is
    // a separate decision (reverse proxy / same-origin deploy).
    //
    // 127.0.0.1, not localhost: Node 17+ resolves localhost to ::1 first,
    // while uvicorn binds IPv4 only by default — the proxy would then fail
    // with ECONNREFUSED against a backend that is demonstrably up.
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/llm': 'http://127.0.0.1:8000',
      '/characters': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
