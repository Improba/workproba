<template>
  <button
    type="button"
    class="wp-theme-toggle"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click="onToggle"
  >
    <Lucide :name="isDark ? 'moon' : 'sun'" size="14" color="accent" />
    <span class="wp-theme-toggle__label">{{ i18n.t('theme') }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useUiTheme } from '@composables/useUiTheme';

const i18n = useI18n();
const { isDark, toggleUiTheme } = useUiTheme();

const ariaLabel = computed(() =>
  isDark.value
    ? i18n.t('themeSwitchToLight')
    : i18n.t('themeSwitchToDark'),
);

async function onToggle(): Promise<void> {
  try {
    await toggleUiTheme();
  } catch {
    Notify.create({
      message: i18n.t('settings.saveFailed'),
      color: 'negative',
      timeout: 4000,
    });
  }
}
</script>

<style scoped lang="scss">
.wp-theme-toggle {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 8px;
  margin: 0;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent-soft);
  cursor: pointer;
  font-family: var(--wp-font-ui);
  transition:
    background 120ms var(--wp-ease),
    border-color 120ms var(--wp-ease);

  &:hover {
    background: var(--wp-surface);
    border-color: var(--wp-border-strong);
  }

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: var(--wp-focus-offset);
  }
}

.wp-theme-toggle__label {
  font-size: 11px;
  line-height: 1;
  color: var(--wp-text-muted);
  white-space: nowrap;
}
</style>
