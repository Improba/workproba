<template>
  <span
    class="wp-cap-status"
    :class="`wp-cap-status--${state.kind}`"
    :title="tooltip"
  >
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { CapabilityState } from '@capabilities/capabilityCatalog';

const props = defineProps<{
  state: CapabilityState;
}>();

const { t } = useI18n();

const label = computed(() => {
  if (props.state.kind === 'blocked' && props.state.managedByOrganization) {
    return t('capabilities.status.managedByOrganization');
  }
  return t(`capabilities.status.${props.state.kind}`);
});

const tooltip = computed(() => label.value);
</script>

<style scoped lang="scss">
.wp-cap-status {
  display: inline-flex;
  align-self: flex-start;
  width: fit-content;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--wp-r-pill);
  font-size: var(--wp-fs-xs);
  font-weight: 500;
  line-height: var(--wp-lh-tight);
  white-space: nowrap;
}

.wp-cap-status--active {
  background: var(--wp-success-soft, color-mix(in srgb, var(--wp-success) 14%, transparent));
  color: var(--wp-success);
}

.wp-cap-status--available {
  background: var(--wp-accent-soft);
  color: var(--wp-accent);
}

.wp-cap-status--needs_setup {
  background: var(--wp-warning-soft, color-mix(in srgb, var(--wp-warning) 14%, transparent));
  color: var(--wp-warning);
}

.wp-cap-status--blocked,
.wp-cap-status--unavailable {
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
}

.wp-cap-status--coming_soon {
  background: var(--wp-surface-3);
  color: var(--wp-text-faint);
}
</style>
