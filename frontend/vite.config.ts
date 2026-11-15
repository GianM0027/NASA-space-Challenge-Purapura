// ABOUTME: Vite configuration of the LunarNav frontend: React plugin and dev proxy to the FastAPI backend
// ABOUTME: Owner: Gian. Backend: uv run uvicorn lunarnav.api.main:app --reload --port 8000

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin /api calls in development: no CORS configuration needed on the backend.
    // LUNARNAV_API_URL points a second dev server at a second backend (parallel sessions).
    proxy: {
      '/api': process.env.LUNARNAV_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
})
