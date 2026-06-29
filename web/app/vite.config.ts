import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { readFileSync } from 'fs'

const BUILD_TIME = Date.now()

export default defineConfig({
  define: {
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
    __APP_ENV__: JSON.stringify('staging'),
  },
  build: {
    outDir: '/usr/share/nginx/html/subskin-staging',
    emptyOutDir: true,
  },
  plugins: [
    vue(),
    {
      name: 'generate-version-json',
      generateBundle() {
        let lastProdBuildTime: number | null = null
        try {
          const prodVersion = JSON.parse(readFileSync('/usr/share/nginx/html/subskin/version.json', 'utf8'))
          lastProdBuildTime = prodVersion.buildTime || null
        } catch {}
        this.emitFile({
          type: 'asset',
          fileName: 'version.json',
          source: JSON.stringify({ buildTime: BUILD_TIME, env: 'staging', lastProdBuildTime }),
        })
      },
    },
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['subskin_logo.png', 'og-image.png', 'icons/*.png'],
      manifest: {
        name: 'SubSkin [STAGING]',
        short_name: 'SubSkin-STG',
        description: 'SubSkin Staging — 测试环境。AI赋能的白癜风知识库与社区平台',
        theme_color: '#1e293b',
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
      workbox: {
        clientsClaim: true,
        navigateFallbackDenylist: [/^\/wiki-content/, /^\/version\.json/],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Never cache authenticated/sensitive API responses or user uploads.
        // NetworkFirst previously cached /api/(community|user|vasi|medical-reports)
        // and CacheFirst cached /uploads/ for 7 days — on a shared device, after
        // logout the previous user's L3 data (病灶照片、报告、社区帖) remained in
        // the SW cache and was retrievable by the next user. NetworkOnly + no
        // cache for these paths ensures every request goes to the network and
        // nothing sensitive is stored in the SW cache.
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/.*\/version\.json/i,
            handler: 'NetworkOnly',
          },
          {
            // All API calls: network-only, never cached.
            urlPattern: /^https?:\/\/.*\/api\/.*/i,
            handler: 'NetworkOnly',
          },
          {
            // User uploads (病灶照片、报告、社区图片等 L3 数据): never cache.
            urlPattern: /^https?:\/\/.*\/uploads\/.*/i,
            handler: 'NetworkOnly',
          },
        ],
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
