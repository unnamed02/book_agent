import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/purchase': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/proxy-image': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/save-message': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  }
})
