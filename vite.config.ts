import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    allowedHosts: ['ray.tail4663f6.ts.net'],
    proxy: { '/health': process.env.VITE_TIER1_API_ORIGIN || 'http://127.0.0.1:8000', '/v1': process.env.VITE_TIER1_API_ORIGIN || 'http://127.0.0.1:8000' },
  },
})
