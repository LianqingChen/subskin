/// <reference types="vite/client" />

declare const __BUILD_TIME__: number
declare const __APP_ENV__: 'staging' | 'production'

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}