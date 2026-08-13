<template>
  <div
    class="specialist-handoff-preview"
    aria-hidden="true"
  >
    <span class="specialist-handoff-preview__label">{{ label }}</span>
    <span class="specialist-handoff-preview__spinner" aria-hidden="true" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
}>();
</script>

<style scoped lang="scss">
.specialist-handoff-preview {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) 0;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  animation: wp-fade-in 220ms var(--wp-ease) both;
}

.specialist-handoff-preview__label {
  flex: 1;
  font-style: italic;
}

.specialist-handoff-preview__spinner {
  flex: 0 0 auto;
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 999px;
  border: 2px solid color-mix(in srgb, var(--wp-gold) 35%, transparent);
  border-top-color: var(--wp-gold);
  animation: specialist-handoff-spin 0.7s linear infinite;
}

@keyframes specialist-handoff-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .specialist-handoff-preview {
    animation: none;
  }

  .specialist-handoff-preview__spinner {
    animation: none;
  }
}
</style>
