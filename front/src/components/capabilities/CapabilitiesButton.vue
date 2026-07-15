<template>
  <button
    type="button"
    class="wp-cap-btn"
    :class="{ 'wp-cap-btn--active': open, 'wp-cap-btn--compact': compact }"
    :aria-label="ariaLabel"
    :title="compact ? ariaLabel : undefined"
    @click="emit('toggle')"
  >
    <Lucide name="layers" size="16" :color="open ? 'accent' : 'text-muted'" />
    <span v-if="!compact" class="wp-cap-btn__label">{{ t('capabilities.hubButton') }}</span>
    <q-tooltip v-if="compact" anchor="bottom middle" self="top middle" :offset="[0, 6]">
      {{ t('capabilities.hubButton') }}
    </q-tooltip>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

defineProps<{
  open?: boolean;
  compact?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle'): void;
}>();

const { t } = useI18n();

const ariaLabel = computed(() => t('capabilities.hubButtonAria'));
</script>

<style scoped lang="scss">
.wp-cap-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-2);
  height: 36px;
  padding: 0 var(--wp-space-2);
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-text-muted);
  cursor: pointer;
  transition: background 120ms var(--wp-ease), color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }

  &--active {
    color: var(--wp-accent);
  }

  &--compact {
    width: 36px;
    padding: 0;
  }
}

.wp-cap-btn__label {
  font-size: var(--wp-fs-sm);
  font-weight: 500;
  white-space: nowrap;
}

@media (min-width: 1180px) {
  .wp-cap-btn:not(.wp-cap-btn--compact) {
    padding: 0 var(--wp-space-2);
  }
}

@media (max-width: 1179px) {
  .wp-cap-btn:not(.wp-cap-btn--compact) .wp-cap-btn__label {
    display: none;
  }

  .wp-cap-btn:not(.wp-cap-btn--compact) {
    width: 36px;
    padding: 0;
  }
}
</style>
