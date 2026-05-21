import { defineConfig } from 'vite'

const backendHttp = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:5000'
const backendWs = backendHttp.replace(/^http/, 'ws')

export default defineConfig({
  server: {
    proxy: {
      '/api': backendHttp,
      '/socket.io': { target: backendWs, ws: true },
      '/ws': { target: backendWs, ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
