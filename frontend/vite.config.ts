import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 8081,
    proxy: {
      '/api': {
        target: 'http://localhost:8100',
        changeOrigin: true,
      },
    },
    allowedHosts: ['pi5'],
  },
})
