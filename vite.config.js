import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/ws': { target: 'ws://localhost:5000', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
