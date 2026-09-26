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

    // Dev-only convenience so the frontend can call relative paths without
    // CORS setup. Production routing is a separate decision (reverse proxy /
    // same-origin deploy).
    //
    // Every backend prefix has to be listed here. A missing one does not
    // fail loudly: Vite answers GET with its own index.html and POST with a
    // bare 404, so the page reports "Not Found" for an endpoint that is
    // running perfectly well one port over. See apps/web-backend/app/main.py
    // for the routers this must stay in step with.
    //
    // 127.0.0.1, not localhost: Node 17+ resolves localhost to ::1 first,
    // while uvicorn binds IPv4 only by default — the proxy would then fail
    // with ECONNREFUSED against a backend that is demonstrably up.
    //
    // Vite refuses any Host header it doesn't recognise (DNS-rebinding
    // protection), which is exactly what a tunnel's random subdomain looks
    // like — a `cloudflared tunnel --url` demo is unreachable without this.
    // Scoped to that one provider rather than opened to any host.
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/llm': 'http://127.0.0.1:8000',
      '/characters': 'http://127.0.0.1:8000',
      '/chats': 'http://127.0.0.1:8000',

      '/health': 'http://127.0.0.1:8000',
    },
  },
})
