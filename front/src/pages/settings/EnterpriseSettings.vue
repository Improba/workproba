<template>
  <div class="enterprise-settings">
    <SettingsSubnav active="enterprise" />

    <header class="enterprise-settings__header">
      <h1 class="enterprise-settings__title">{{ t('enterprise.pageTitle') }}</h1>
      <p class="enterprise-settings__subtitle">{{ t('enterprise.pageSubtitle') }}</p>
    </header>

    <section v-if="loading" class="enterprise-settings__empty">
      {{ t('common.loading') }}
    </section>

    <template v-else>
      <section v-if="presetActive && preset" class="enterprise-settings__locked">
        <div class="enterprise-settings__banner">
          <Lucide name="lock" size="20" color="text-muted" />
          <p>{{ t('enterprise.lockedBanner') }}</p>
        </div>

        <h2 class="enterprise-settings__section-title">
          {{ t('enterprise.constraintsTitle') }}
        </h2>
        <ul class="enterprise-settings__constraints" role="list">
          <li v-if="preset.localeLocked">
            {{ t('enterprise.constraintLocale', { locale: localeLabel }) }}
          </li>
          <li v-if="preset.providerSetsLocked">
            {{ t('enterprise.constraintProviderSets') }}
          </li>
          <li v-if="preset.pluginsAllowed?.length">
            {{ t('enterprise.constraintPlugins', { list: preset.pluginsAllowed.join(', ') }) }}
          </li>
          <li v-if="preset.localPluginsAllowed === false">
            {{ t('enterprise.constraintLocalPlugins') }}
          </li>
          <li>
            {{ preset.permissionsNetwork
              ? t('enterprise.constraintNetworkAllowed')
              : t('enterprise.constraintNetworkBlocked') }}
          </li>
          <li>
            {{ preset.codeExecute
              ? t('enterprise.constraintCodeExecuteAllowed')
              : t('enterprise.constraintCodeExecuteBlocked') }}
          </li>
          <li v-if="preset.auditEnabled">
            {{ t('enterprise.constraintAudit', { days: preset.auditRetentionDays ?? 90 }) }}
          </li>
        </ul>
      </section>

      <section v-else class="enterprise-settings__free">
        <p>{{ t('enterprise.freeMode') }}</p>
      </section>

      <section v-if="canExportPreset" class="enterprise-settings__export">
        <h2 class="enterprise-settings__section-title">
          {{ t('enterprise.exportPreset') }}
        </h2>
        <p class="enterprise-settings__export-hint">{{ t('enterprise.exportPresetHint') }}</p>
        <button
          type="button"
          class="enterprise-settings__export-btn"
          :disabled="exporting"
          @click="onExportPreset"
        >
          <Lucide name="download" size="16" color="text-muted" />
          {{ exporting ? t('common.loading') : t('enterprise.exportPreset') }}
        </button>
      </section>

      <AuditPanel :workspace-data-dir="workspaceDataDir" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import SettingsSubnav from '@components/settings/SettingsSubnav.vue';
import AuditPanel from '@components/settings/AuditPanel.vue';
import { useEnterprise } from '@composables/useEnterprise';
import { useSpace } from '@composables/useSpace';
import { useAppSettings } from '@composables/useAppSettings';
import { exportEnterprisePreset } from '@composables/useDesktop';

const { t } = useI18n();
const { presetActive, preset, loading, refresh } = useEnterprise();
const { activeDataDir } = useSpace();
const { settingsMode, settingsLocked } = useAppSettings();

const exporting = ref(false);
const canExportPreset = computed(
  () => settingsMode.value === 'advanced' && !settingsLocked.value,
);

const workspaceDataDir = computed(() => activeDataDir.value);

const localeLabel = computed(() => {
  const value = preset.value?.locale;
  if (value === 'en-US') return t('common.languageEn');
  if (value === 'fr') return t('common.languageFr');
  return value ?? t('enterprise.constraintLocaleAuto');
});

onMounted(() => {
  void refresh();
});

async function onExportPreset(): Promise<void> {
  if (exporting.value) return;
  exporting.value = true;
  try {
    const path = await exportEnterprisePreset();
    if (!path) {
      Notify.create({
        message: t('enterprise.exportPresetCancelled'),
        color: 'dark',
        timeout: 2000,
      });
      return;
    }
    Notify.create({
      message: t('enterprise.exportPresetSuccess', { path }),
      color: 'dark',
      timeout: 3000,
    });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('enterprise.exportPresetFailed'),
      classes: 'bg-danger text-white',
    });
  } finally {
    exporting.value = false;
  }
}
</script>

<style scoped lang="scss">
.enterprise-settings {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  padding: 1rem 24px 1.25rem;
  box-sizing: border-box;
  background: var(--wp-bg);
  font-family: var(--wp-font-ui);
  overflow-y: auto;
}

.enterprise-settings__header {
  margin-bottom: 0.75rem;
}

.enterprise-settings__title {
  margin: 0 0 0.25rem;
  font-family: var(--wp-font-head);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wp-text);
}

.enterprise-settings__subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.enterprise-settings__empty {
  padding: 16px 4px;
  color: var(--wp-text-faint);
}

.enterprise-settings__locked,
.enterprise-settings__free {
  margin-bottom: 1.25rem;
}

.enterprise-settings__banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  margin-bottom: 12px;
}

.enterprise-settings__section-title {
  margin: 0 0 8px;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.enterprise-settings__constraints {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
  line-height: var(--wp-lh-relaxed);
}

.enterprise-settings__free p {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-sm);
}

.enterprise-settings__export {
  margin-bottom: 1.25rem;
}

.enterprise-settings__export-hint {
  margin: 0 0 10px;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.enterprise-settings__export-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-surface-2);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
