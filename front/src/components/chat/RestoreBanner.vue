<template>
  <div class="restore-banner" data-testid="restore-banner" role="status">
    <span class="restore-banner__text">{{ t('shell.versions.restauré') }}</span>
    <button
      type="button"
      class="restore-banner__action"
      :disabled="busy"
      :aria-label="t('shell.versions.annulerRestauration')"
      @click="emit('undo')"
    >
      {{ busy ? t('common.inProgress') : t('shell.versions.annulerRestauration') }}
    </button>
    <button
      type="button"
      class="restore-banner__dismiss"
      :aria-label="t('common.close')"
      @click="emit('dismiss')"
    >
      <Lucide name="x" size="14" color="text-muted" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

defineProps<{
  busy?: boolean;
}>();

const emit = defineEmits<{
  undo: [];
  dismiss: [];
}>();

const { t } = useI18n();
</script>

<style scoped lang="scss">
.restore-banner {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem 0.65rem;
  margin-top: 0.45rem;
  padding: 0.45rem 0.65rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent-soft);
  border: 1px solid var(--wp-accent);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}

.restore-banner__text {
  flex: 1 1 auto;
  min-width: 0;
  font-weight: 600;
}

.restore-banner__action {
  flex: 0 0 auto;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }
}

.restore-banner__dismiss {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.15rem;
}
</style>
