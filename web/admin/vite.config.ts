import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

let buildBase = '/'
const buildTime = Date.now()

export default defineConfig({
  plugins: [vue(), tailwindcss(), {
    name: 'admin-build-version',
    configResolved(config) { buildBase = config.base },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'version.json', source: JSON.stringify({
        buildTime, env: buildBase === '/admin-preview/' ? 'admin-preview' : 'admin',
      }) })
    },
  }],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  build: {
    outDir: '/usr/share/nginx/html/subskin-admin',
    emptyOutDir: true
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
