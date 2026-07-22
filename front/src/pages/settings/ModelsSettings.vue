<template>
  <div class="models-settings" :class="{ 'models-settings--locked': settingsLocked }">
    <div class="models-settings__inner">
      <SettingsSubnav active="models" />

      <header class="models-settings__header">
        <div>
          <h1 class="models-settings__title">{{ t('settings.title') }}</h1>
          <p class="models-settings__subtitle">
            {{ t('settings.subtitle') }}
          </p>
        </div>
      </header>

      <section v-if="loading" class="models-settings__empty">{{ t('common.loading') }}</section>

      <template v-else>
        <LanguageControl />
        <DensityControl />

        <LockedModelSetup v-if="settingsLocked" />

        <fieldset v-else class="models-settings__body">
          <AdvancedModelSetup />
        </fieldset>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useAppSettings } from '@composables/useAppSettings';
import AdvancedModelSetup from '@components/settings/AdvancedModelSetup.vue';
import LockedModelSetup from '@components/settings/LockedModelSetup.vue';
import DensityControl from '@components/settings/DensityControl.vue';
import LanguageControl from '@components/settings/LanguageControl.vue';
import SettingsSubnav from '@components/settings/SettingsSubnav.vue';

const { t } = useI18n();

const {
  load,
  settingsLocked,
} = useAppSettings();

const loading = ref(true);

onMounted(async () => {
  try {
    await load();
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped lang="scss">
.models-settings {
  height: 100%;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
  overflow-x: hidden;
  overflow-y: auto;
}

.models-settings__inner {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  padding: 1rem 24px 1.25rem;
  box-sizing: border-box;
}

.models-settings__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--wp-border);
  margin-bottom: 1rem;
}

.models-settings__title {
  margin: 0 0 0.25rem;
  font-family: var(--wp-font-head);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wp-text);
}

.models-settings__subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.models-settings__empty {
  padding: 24px 4px;
  color: var(--wp-text-faint);
  font-size: 14px;
}

.models-settings__body {
  border: none;
  margin: 0;
  padding: 0;
  min-width: 0;
}

.models-settings--locked .models-settings__header {
  opacity: 0.6;
}
</style>
