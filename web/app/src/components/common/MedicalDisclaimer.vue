<script setup lang="ts">
/**
 * Unified medical disclaimer banner.
 * MUST appear on every content page — required for compliance.
 */
withDefaults(defineProps<{
  /** Variant: 'banner' (amber background) | 'inline' (text-only) | 'footer' (small text with border) */
  variant?: 'banner' | 'inline' | 'footer'
  /** Custom message override (falls back to standard disclaimer) */
  message?: string
}>(), {
  variant: 'inline',
  message: '',
})

const defaultMessage = '本平台不构成医疗建议，所有内容仅供参考。具体诊疗请遵医嘱。'
</script>

<template>
  <!-- Banner variant (amber bg) -->
  <div
    v-if="variant === 'banner'"
    class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-lg p-3 flex items-start gap-2"
  >
    <span class="text-amber-500 text-sm mt-0.5"><i class="ri-error-warning-line"></i></span>
    <p class="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
      {{ message || defaultMessage }}
    </p>
  </div>

  <!-- Inline variant (text centered) -->
  <p
    v-else-if="variant === 'inline'"
    class="text-xs text-gray-400  text-center"
  >
    {{ message || defaultMessage }}
  </p>

  <!-- Footer variant (with border top) -->
  <section
    v-else
    class="text-center text-xs text-gray-400  py-4 border-t border-gray-100 dark:border-gray-800"
  >
    {{ message || defaultMessage }}
  </section>
</template>
