<template>
  <button
    type="button"
    class="open-folder-btn"
    :disabled="loading"
    @click="emit('click')"
  >
    <Lucide name="folder-open" size="sm" color="text-invert" />
    <span>{{ label }}</span>
    <q-spinner v-if="loading" size="18px" class="open-folder-btn__spinner" />
  </button>
</template>

<script setup lang="ts">
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

withDefaults(
  defineProps<{
    loading?: boolean;
    label?: string;
  }>(),
  {
    loading: false,
    label: 'Ouvrir un dossier',
  },
);

const emit = defineEmits<{
  click: [];
}>();
</script>

<style scoped lang="scss">
.open-folder-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  border: none;
  border-radius: var(--wp-r-md);
  background: var(--wp-primary);
  color: var(--text-invert);
  font-size: 0.92rem;
  font-weight: 600;
  font-family: var(--wp-font-ui);
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease),
    transform var(--wp-dur) var(--wp-ease);

  &:hover:not(:disabled) {
    background: var(--primary-high);
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.open-folder-btn__spinner {
  color: var(--text-invert);
}
</style>
