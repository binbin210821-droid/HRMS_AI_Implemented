/* global process */
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const backendOrigin = env.VITE_DEV_API_ORIGIN || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': backendOrigin,
        '/ws': {
          target: backendOrigin.replace(/^http/, 'ws'),
          ws: true,
        },
      },
    },
    preview: {
      proxy: {
        '/api': backendOrigin,
        '/ws': {
          target: backendOrigin.replace(/^http/, 'ws'),
          ws: true,
        },
      },
    },
  }
})
