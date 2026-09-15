import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Server-only environment: Docker addresses the backend service; native Vite uses loopback.
// Production serves the compiled dist directory and does not run this proxy.
const backend = process.env.AMANDAYE_DEV_API_TARGET || 'http://127.0.0.1:8000'
const backendUrl = new URL(backend)
if (!['http:', 'https:'].includes(backendUrl.protocol) || backendUrl.username || backendUrl.password) {
  throw new Error('AMANDAYE_DEV_API_TARGET must be an HTTP(S) origin without credentials')
}
const backendProxy = Object.fromEntries(
  ['/api/', '/login/', '/admin/', '/apps/', '/static/', '/media/'].map(
    (path) => [path, { target: backend }],
  ),
)

export default defineConfig({
  cacheDir: process.env.AMANDAYE_VITE_CACHE_DIR || 'node_modules/.vite',
  plugins: [
    vue(),
    tailwindcss(),
  ],
  server: {
    watch: {
      usePolling: true,
      interval: 1000,
    },
    host: '127.0.0.1',
    strictPort: true,
    proxy: backendProxy,
  },
  preview: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: backendProxy,
  },
})
