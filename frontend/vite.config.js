import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/static': 'http://localhost:8000'
    }
  },
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: false
  }
});
