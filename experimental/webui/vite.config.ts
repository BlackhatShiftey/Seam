import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  publicDir: 'public',
  server: {
    port: 5173,
    proxy: {
      // Direct endpoint proxies for the dashboard HTML (no /api prefix rewrite needed)
      '/health': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/stats': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/compile': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/compile-dsl': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/search': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/context': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/persist': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/lossless-compress': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/tree': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/benchmark': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/sys-metrics': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/trace': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      // Keep the /api prefix proxy for the existing TS panes
      '/api': {
        target: process.env.SEAM_API_URL || 'http://127.0.0.1:8765',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
