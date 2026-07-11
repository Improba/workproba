<template>
  <nav class="settings-subnav" :aria-label="t('settings.plugins.navLabel')">
    <router-link
      :to="{ name: 'settings_models' }"
      class="settings-subnav__link"
      :class="{ 'settings-subnav__link--active': active === 'models' }"
    >
      {{ t('settings.plugins.navModels') }}
    </router-link>
    <router-link
      :to="{ name: 'settings_plugins' }"
      class="settings-subnav__link"
      :class="{ 'settings-subnav__link--active': active === 'plugins' }"
    >
      {{ pluginsNavLabel }}
    </router-link>
    <router-link
      :to="{ name: 'settings_enterprise' }"
      class="settings-subnav__link"
      :class="{ 'settings-subnav__link--active': active === 'enterprise' }"
    >
      {{ t('enterprise.navTitle') }}
    </router-link>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useAppSettings } from '@composables/useAppSettings';

defineProps<{
  active: 'models' | 'plugins' | 'enterprise';
}>();

const { t } = useI18n();
const { settingsMode, settingsLocked } = useAppSettings();

const pluginsNavLabel = computed(() =>
  settingsMode.value === 'advanced' && !settingsLocked.value
    ? t('settings.plugins.navTitleAdvanced')
    : t('settings.plugins.navTitle'),
);
</script>

<style scoped lang="scss">
.settings-subnav {
  display: flex;
  gap: var(--wp-space-2);
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--wp-border);
}

.settings-subnav__link {
  padding: var(--wp-space-2) var(--wp-space-3);
  border-radius: var(--wp-r-sm);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  text-decoration: none;
  transition: background var(--wp-dur) var(--wp-ease), color var(--wp-dur) var(--wp-ease);

  &:hover {
    background: var(--wp-surface-2);
    color: var(--wp-text);
  }

  &--active {
    background: var(--wp-accent-soft);
    color: var(--wp-accent);
    font-weight: 600;
  }
}
</style>
