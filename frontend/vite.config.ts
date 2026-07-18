import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 生产环境 build 时 base 为 /，前端 build 产物由 FastAPI 托管
  base: '/',
  server: {
    port: 5173,
    proxy: {
      // 本地开发时代理到后端
      '/api/readings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/api/portrait': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/api/synastry': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  }
})

