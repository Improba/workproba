<template>
  <div class="plugins-panel">
    <header class="plugins-panel__header">
      <h2 class="plugins-panel__title">{{ panelTitle }}</h2>
      <p class="plugins-panel__subtitle">{{ panelSubtitle }}</p>
    </header>

    <section v-if="loading" class="plugins-panel__empty">
      {{ t('common.loading') }}
    </section>

    <section v-else-if="loadError" class="plugins-panel__empty plugins-panel__empty--error">
      <Lucide name="alert-triangle" size="22" color="danger" />
      <p>{{ t('settings.plugins.loadFailed') }}</p>
      <button type="button" class="plugins-panel__retry" @click="refresh">
        {{ t('common.retry') }}
      </button>
    </section>

    <section v-else-if="plugins.length === 0 && !isDesktopApp()" class="plugins-panel__empty">
      <p>{{ t('settings.plugins.desktopOnly') }}</p>
    </section>

    <section v-else-if="plugins.length === 0" class="plugins-panel__empty">
      <p>{{ t('settings.plugins.empty') }}</p>
    </section>

    <ul v-else class="plugins-panel__list" role="list">
      <li
        v-for="plugin in visiblePlugins"
        :key="plugin.manifest.id"
        class="plugins-panel__card"
        :class="{ 'plugins-panel__card--upcoming': isUpcomingPlugin(plugin) }"
      >
        <div class="plugins-panel__card-head">
          <div class="plugins-panel__card-info">
            <h3 class="plugins-panel__card-title">{{ pluginLabel(plugin) }}</h3>
            <span class="plugins-panel__version">{{ t('settings.plugins.version', { version: plugin.manifest.version }) }}</span>
            <span
              v-if="showAdvanced"
              class="plugins-panel__source"
              :class="`plugins-panel__source--${plugin.source}`"
            >
              {{ sourceLabel(plugin.source) }}
            </span>
            <span
              v-if="isUpcomingPlugin(plugin)"
              class="plugins-panel__upcoming"
              :title="upcomingTooltip(plugin)"
            >
              {{ t('settings.plugins.upcoming') }}
            </span>
            <span
              v-if="isPreinstalledPlugin(plugin)"
              class="plugins-panel__preinstalled"
            >
              {{ t('settings.plugins.sourceBuiltin') }}
            </span>
          </div>
          <q-toggle
            v-if="canToggle(plugin)"
            :model-value="plugin.enabledScoped && !isUpcomingPlugin(plugin)"
            :disable="togglingId === plugin.manifest.id || isUpcomingPlugin(plugin)"
            :aria-label="toggleAria(plugin)"
            @update:model-value="(v: boolean) => onToggle(plugin, v)"
          />
          <div v-else-if="isManagedByCapability(plugin)" class="plugins-panel__managed">
            <span class="plugins-panel__locked">
              {{ managedByCapabilityLabel(plugin) }}
            </span>
            <span class="plugins-panel__locked">
              {{ plugin.enabledScoped ? t('settings.plugins.statusActive') : t('settings.plugins.statusInactive') }}
            </span>
            <button
              v-if="capabilityForPlugin(plugin)"
              type="button"
              class="plugins-panel__open-cap"
              @click="openPluginInCapabilities(plugin)"
            >
              {{ t('settings.plugins.openInCapabilities') }}
            </button>
          </div>
          <span v-else-if="settingsLocked" class="plugins-panel__locked">
            {{ plugin.enabledScoped ? t('settings.plugins.statusActive') : t('settings.plugins.statusInactive') }}
          </span>
        </div>

        <p class="plugins-panel__description">{{ pluginDescription(plugin) }}</p>

        <details v-if="showAdvanced && plugin.manifest.permissions.length" class="plugins-panel__perms">
          <summary>{{ t('settings.plugins.permissions') }}</summary>
          <ul>
            <li v-for="perm in plugin.manifest.permissions" :key="perm">{{ perm }}</li>
          </ul>
        </details>

        <div
          v-if="showAdvanced && plugin.source === 'local' && !settingsLocked"
          class="plugins-panel__actions"
        >
          <button
            type="button"
            class="plugins-panel__uninstall"
            :disabled="uninstallingId === plugin.manifest.id"
            @click="onUninstall(plugin.manifest.id)"
          >
            {{ t('settings.plugins.uninstall') }}
          </button>
        </div>
      </li>
    </ul>

    <footer
      v-if="showAdvanced && !settingsLocked && localPluginInstallAvailable()"
      class="plugins-panel__footer"
    >
      <button
        type="button"
        class="plugins-panel__install"
        :disabled="installing"
        @click="onInstallLocal"
      >
        <Lucide name="folder-plus" size="15" color="accent" />
        <span>{{ t('settings.plugins.installLocal') }}</span>
      </button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { getCapabilityForPlugin } from '@capabilities/capabilityCatalog';
import type { CapabilityDefinition } from '@capabilities/capabilityCatalog';
import { useAppSettings } from '@composables/useAppSettings';
import { pickProjectFolder, isDesktopApp } from '@composables/useDesktop';
import { useShellSurfaces } from '@composables/useShellSurfaces';
import {
  isUpcomingPluginId,
  BROWSER_PLUGIN_ID,
  CLOUD_PLUGIN_ID,
  localPluginInstallAvailable,
  PERSONAS_PLUGIN_ID,
  usePlugins,
} from '@composables/usePlugins';
import type { PluginInfo, PluginSource } from '@composables/useDesktop.types';

const { t, te } = useI18n();
const { settingsMode, settingsLocked } = useAppSettings();
const { openCapabilities } = useShellSurfaces();
const {
  plugins,
  loading,
  loadError,
  refresh,
  activatePlugin,
  deactivatePlugin,
  installLocalPlugin,
  uninstallLocalPlugin,
} = usePlugins();

const togglingId = ref<string | null>(null);
const installing = ref(false);
const uninstallingId = ref<string | null>(null);

const showAdvanced = computed(
  () => settingsMode.value === 'advanced' && !settingsLocked.value,
);

const panelTitle = computed(() =>
  showAdvanced.value
    ? t('settings.plugins.titleAdvanced')
    : t('settings.plugins.title'),
);

const panelSubtitle = computed(() =>
  showAdvanced.value
    ? t('settings.plugins.subtitleAdvanced')
    : t('settings.plugins.subtitle'),
);

const visiblePlugins = computed(() => {
  if (showAdvanced.value) {
    return plugins.value;
  }
  return plugins.value.filter((plugin) => plugin.manifest.id !== CLOUD_PLUGIN_ID);
});

function capabilityForPlugin(plugin: PluginInfo): CapabilityDefinition | undefined {
  return getCapabilityForPlugin(plugin.manifest.id);
}

function capabilityTitle(plugin: PluginInfo): string {
  const capability = capabilityForPlugin(plugin);
  if (!capability) return pluginLabel(plugin);
  return te(capability.titleKey) ? t(capability.titleKey) : capability.titleKey;
}

function managedByCapabilityLabel(plugin: PluginInfo): string {
  return t('settings.plugins.managedByCapability', {
    name: capabilityTitle(plugin),
  });
}

function isManagedByCapability(plugin: PluginInfo): boolean {
  if (plugin.source === 'builtin') return true;
  return showAdvanced.value && plugin.manifest.id === CLOUD_PLUGIN_ID;
}

function openPluginInCapabilities(plugin: PluginInfo): void {
  const capability = capabilityForPlugin(plugin);
  if (capability) {
    openCapabilities(capability.id);
  }
}

function isUpcomingPlugin(plugin: PluginInfo): boolean {
  return isUpcomingPluginId(plugin.manifest.id);
}

function isPreinstalledPlugin(plugin: PluginInfo): boolean {
  return (
    (plugin.manifest.id === PERSONAS_PLUGIN_ID ||
      plugin.manifest.id === BROWSER_PLUGIN_ID) &&
    plugin.source === 'builtin'
  );
}

function upcomingTooltip(plugin: PluginInfo): string {
  if (plugin.manifest.id === 'workproba.browser') {
    return t('settings.plugins.upcomingTooltipBrowser');
  }
  return t('settings.plugins.upcomingTooltip');
}

function pluginLabel(plugin: PluginInfo): string {
  const key = plugin.manifest.name;
  return te(key) ? t(key) : key;
}

function pluginDescription(plugin: PluginInfo): string {
  const key = plugin.manifest.description;
  return te(key) ? t(key) : key;
}

function sourceLabel(source: PluginSource): string {
  return source === 'builtin'
    ? t('settings.plugins.sourceBuiltin')
    : t('settings.plugins.sourceLocal');
}

function canToggle(plugin: PluginInfo): boolean {
  if (settingsLocked.value) return false;
  if (isUpcomingPlugin(plugin)) return false;
  if (plugin.source === 'builtin') return false;
  return plugin.source === 'local';
}

function toggleAria(plugin: PluginInfo): string {
  if (isUpcomingPlugin(plugin)) {
    return t('settings.plugins.upcoming');
  }
  return plugin.enabledScoped
    ? t('settings.plugins.deactivate', { name: pluginLabel(plugin) })
    : t('settings.plugins.activate', { name: pluginLabel(plugin) });
}

async function onToggle(plugin: PluginInfo, enabled: boolean): Promise<void> {
  if (isUpcomingPlugin(plugin)) {
    Notify.create({
      message: t('settings.plugins.upcoming'),
      color: 'info',
      timeout: 3500,
    });
    return;
  }

  togglingId.value = plugin.manifest.id;
  try {
    if (enabled) {
      await activatePlugin(plugin.manifest.id);
    } else {
      await deactivatePlugin(plugin.manifest.id);
    }
  } catch (err) {
    const message =
      err instanceof Error && err.message === 'plugin_upcoming'
        ? t('settings.plugins.upcoming')
        : err instanceof Error
          ? err.message
          : t('settings.plugins.toggleFailed');
    Notify.create({
      message,
      color: 'negative',
    });
  } finally {
    togglingId.value = null;
  }
}

async function onInstallLocal(): Promise<void> {
  installing.value = true;
  try {
    const folder = await pickProjectFolder();
    if (!folder) return;
    await installLocalPlugin(folder);
    Notify.create({
      message: t('settings.plugins.installSuccess'),
      color: 'positive',
      timeout: 2000,
    });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.plugins.installFailed'),
      color: 'negative',
    });
  } finally {
    installing.value = false;
  }
}

async function onUninstall(id: string): Promise<void> {
  uninstallingId.value = id;
  try {
    await uninstallLocalPlugin(id);
    Notify.create({
      message: t('settings.plugins.uninstallSuccess'),
      color: 'positive',
      timeout: 2000,
    });
  } catch (err) {
    Notify.create({
      message: err instanceof Error ? err.message : t('settings.plugins.uninstallFailed'),
      color: 'negative',
    });
  } finally {
    uninstallingId.value = null;
  }
}

onMounted(() => {
  void refresh();
});
</script>

<style scoped lang="scss">
.plugins-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.plugins-panel__header {
  margin-bottom: 0.25rem;
}

.plugins-panel__title {
  margin: 0 0 0.25rem;
  font-family: var(--wp-font-head);
  font-size: 1rem;
  font-weight: 700;
  color: var(--wp-text);
}

.plugins-panel__subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  max-width: 56ch;
}

.plugins-panel__empty {
  padding: 24px 4px;
  color: var(--wp-text-faint);
  font-size: 14px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.plugins-panel__empty--error {
  color: var(--wp-danger);
}

.plugins-panel__retry {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  cursor: pointer;
  font-size: var(--wp-fs-xs);
}

.plugins-panel__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plugins-panel__card {
  padding: 14px 16px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);

  &--upcoming {
    opacity: 0.72;
    background: var(--wp-surface-2);
  }
}

.plugins-panel__card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.plugins-panel__card-info {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.plugins-panel__card-title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--wp-text);
}

.plugins-panel__version {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.plugins-panel__source {
  font-size: var(--wp-fs-xs);
  padding: 1px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);

  &--local {
    background: var(--wp-accent-soft);
    color: var(--wp-accent);
  }
}

.plugins-panel__upcoming {
  font-size: var(--wp-fs-xs);
  padding: 1px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft, var(--wp-surface-3));
  color: var(--wp-gold, var(--wp-text-muted));
  font-weight: 600;
}

.plugins-panel__experimental {
  font-size: var(--wp-fs-xs);
  padding: 1px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-accent-soft);
  color: var(--wp-accent);
  font-weight: 600;
}

.plugins-panel__preinstalled {
  font-size: var(--wp-fs-xs);
  padding: 1px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft, var(--wp-surface-3));
  color: var(--wp-gold, var(--wp-text-muted));
  font-weight: 600;
}

.plugins-panel__description {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--wp-text-muted);
  line-height: var(--wp-lh-relaxed);
}

.plugins-panel__locked {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.plugins-panel__managed {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.plugins-panel__open-cap {
  padding: var(--wp-space-1) var(--wp-space-2);
  border: none;
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;

  &:hover {
    color: var(--wp-text);
  }
}

.plugins-panel__perms {
  margin-top: 10px;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);

  summary {
    cursor: pointer;
    color: var(--wp-text-faint);
  }

  ul {
    margin: 6px 0 0;
    padding-left: 1.25rem;
  }
}

.plugins-panel__actions {
  margin-top: 10px;
}

.plugins-panel__uninstall {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-danger);
  font-size: var(--wp-fs-xs);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: color-mix(in srgb, var(--wp-danger) 8%, transparent);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.plugins-panel__footer {
  padding-top: 8px;
  border-top: 1px solid var(--wp-border);
}

.plugins-panel__install {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px dashed var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: transparent;
  color: var(--wp-accent);
  font-size: var(--wp-fs-sm);
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--wp-accent-soft);
    border-color: var(--wp-accent);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>
