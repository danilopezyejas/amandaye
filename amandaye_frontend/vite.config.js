import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Native development only. Production serves the compiled dist directory.
const backend = 'http://127.0.0.1:8000'
const backendProxy = Object.fromEntries(
  ['/api/', '/login/', '/admin/', '/apps/', '/static/', '/media/'].map(
    (path) => [path, { target: backend }],
  ),
)

export default defineConfig({
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
