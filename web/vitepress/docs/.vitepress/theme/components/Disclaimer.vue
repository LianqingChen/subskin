<template>
  <div class="custom-disclaimer">
    <div class="custom-disclaimer-title">⚠️ 免责声明</div>
    <slot></slot>
  </div>
</template>

<style scoped>
.custom-disclaimer {
  background-color: var(--subskin-color-bg-soft);
  border-left: 4px solid var(--subskin-color-warning);
  border-radius: var(--subskin-radius-md);
  padding: var(--subskin-space-4);
  margin: var(--subskin-space-6) 0;
}

.custom-disclaimer-title {
  font-weight: 600;
  color: var(--subskin-color-warning);
  margin-bottom: var(--subskin-space-2);
}
</style>
