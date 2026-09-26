import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The Flask API runs inside WSL on port 5000; WSL forwards localhost to Windows.
// Proxying /api keeps the browser on one origin, so no CORS round-trips in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: process.env.API_URL ?? 'http://127.0.0.1:5000', changeOrigin: true },
    },
  },
})
