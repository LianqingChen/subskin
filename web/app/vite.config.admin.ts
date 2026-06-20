/**
 * ⛔ DEPRECATED — DO NOT USE
 *
 * This file was the OLD way of building the admin panel by re-using the main
 * app (web/app/) with admin-flavored config. That approach caused the admin
 * panel at admin.subskin.cn to look identical to staging/production, creating
 * confusion about which environment was which.
 *
 * The admin panel is now a STANDALONE project at web/admin/ with its own:
 *   - Login page (/#/login)
 *   - UI framework (NaiveUI, not main-app PWA)
 *   - Hash routing (not history mode)
 *   - Build config (web/admin/vite.config.ts)
 *
 * Build command for admin:  cd /root/subskin/web/admin && npx vite build
 * Deploy target:             /usr/share/nginx/html/subskin-admin/
 *
 * See AGENTS.md § "Three-Environment Architecture" for the full rules.
 *
 * If you're reading this and about to run `npx vite build --config vite.config.admin.ts`:
 *   STOP. Go to web/admin/ and run `npx vite build` instead.
 */
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
    outDir: '/usr/share/nginx/html/subskin-admin',
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
          source: JSON.stringify({ buildTime: BUILD_TIME, env: 'admin' }),
        })
      },
    },
    VitePWA({
      registerType: 'prompt',
      includeAssets: ['subskin_logo.png', 'og-image.png', 'icons/*.png'],
      manifest: {
        name: 'SubSkin Admin',
        short_name: 'SubSkin管理',
        description: 'SubSkin 管理后台 — 数据标注与运营管理',
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
        navigateFallbackDenylist: [/^\/version\.json/],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/.*\/version\.json/i,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 3 },
              networkTimeoutSeconds: 5,
            },
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
})
