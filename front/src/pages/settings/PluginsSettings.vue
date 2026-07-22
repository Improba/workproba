<template>
  <div class="plugins-settings">
    <div class="plugins-settings__inner">
      <SettingsSubnav active="plugins" />

      <header class="plugins-settings__header">
        <h1 class="plugins-settings__title">{{ pageTitle }}</h1>
      </header>

      <PluginsPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useAppSettings } from '@composables/useAppSettings';
import SettingsSubnav from '@components/settings/SettingsSubnav.vue';
import PluginsPanel from '@components/settings/PluginsPanel.vue';

const { t } = useI18n();
const { settingsLocked } = useAppSettings();

const pageTitle = computed(() =>
  !settingsLocked.value
    ? t('settings.plugins.pageTitleAdvanced')
    : t('settings.plugins.pageTitle'),
);
</script>

<style scoped lang="scss">
.plugins-settings {
  height: 100%;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
  overflow-x: hidden;
  overflow-y: auto;
}

.plugins-settings__inner {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  padding: 1rem 24px 1.25rem;
  box-sizing: border-box;
}

.plugins-settings__header {
  margin-bottom: 0.5rem;
}

.plugins-settings__title {
  margin: 0;
  font-family: var(--wp-font-head);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wp-text);
}
</style>
