import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // /auth is the Auth0 login flow, served by the API (same origin keeps the session cookie).
    proxy: {
      '/api': `http://127.0.0.1:${process.env.GHOST_API_PORT ?? 8765}`,
      '/auth': `http://127.0.0.1:${process.env.GHOST_API_PORT ?? 8765}`,
    },
  },
})
