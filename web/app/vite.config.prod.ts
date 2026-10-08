import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

const BUILD_TIME = Date.now()

export default defineConfig({
  define: {
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
    __APP_ENV__: JSON.stringify('production'),
  },
  build: {
    outDir: '/usr/share/nginx/html/subskin',
    emptyOutDir: true,
  },
  plugins: [
    vue(),
    {
      name: 'generate-version-json',
      generateBundle() {
        this.emitFile({
          type: 'asset',
          fileName: 'version.json',
          source: JSON.stringify({ buildTime: BUILD_TIME, env: 'production' }),
        })
      },
    },
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['subskin_logo.png', 'og-image.png', 'icons/*.png'],
      manifest: {
        name: 'SubSkin - 白癜风病友的AI记录和分享社区',
        short_name: 'SubSkin',
        description: '白癜风病友的AI记录和分享社区',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait-primary',
        scope: './',
        start_url: './',
        categories: ['medical', 'health'],
        icons: [
          { src: './icons/icon-72x72.png?v=c7f3a2', sizes: '72x72', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-96x96.png?v=c7f3a2', sizes: '96x96', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-128x128.png?v=c7f3a2', sizes: '128x128', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-144x144.png?v=c7f3a2', sizes: '144x144', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-152x152.png?v=c7f3a2', sizes: '152x152', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-192x192.png?v=c7f3a2', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-384x384.png?v=c7f3a2', sizes: '384x384', type: 'image/png', purpose: 'any' },
          { src: './icons/icon-512x512.png?v=c7f3a2', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: './icons/maskable-512x512.png?v=c7f3a2', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: undefined,
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      injectManifest: {
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: ['**/*.{js,css,html,ico,png,svg,webp,woff2}'],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
