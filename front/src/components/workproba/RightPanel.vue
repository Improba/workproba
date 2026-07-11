<template>
  <aside class="wp-right-panel" :class="{ 'wp-right-panel--collapsed': !open }">
    <div v-if="open" class="wp-right-panel__inner">
      <div class="wp-right-panel__tabs" role="tablist">
        <button
          type="button"
          role="tab"
          class="wp-right-panel__tab"
          :class="{ 'wp-right-panel__tab--active': activeTab === 'files' }"
          :aria-selected="activeTab === 'files'"
          :aria-label="t('shell.fileTreeLabel')"
          @click="activeTab = 'files'"
        >
          <Lucide name="folder-tree" size="15" :color="activeTab === 'files' ? 'accent' : 'text-muted'" />
          <span class="wp-right-panel__tab-label">{{ t('shell.filesTab') }}</span>
        </button>
        <button
          type="button"
          role="tab"
          class="wp-right-panel__tab"
          :class="{ 'wp-right-panel__tab--active': activeTab === 'preview' }"
          :aria-selected="activeTab === 'preview'"
          :aria-label="t('shell.preview')"
          @click="activeTab = 'preview'"
        >
          <Lucide name="eye" size="15" :color="activeTab === 'preview' ? 'accent' : 'text-muted'" />
          <span class="wp-right-panel__tab-label">{{ t('shell.preview') }}</span>
        </button>
        <button
          v-for="tab in rightPanelPluginTabs"
          :key="tab.key"
          type="button"
          role="tab"
          class="wp-right-panel__tab"
          :class="{ 'wp-right-panel__tab--active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          :aria-label="tab.label"
          @click="activeTab = tab.key"
        >
          <Lucide :name="tab.icon" size="15" :color="activeTab === tab.key ? 'accent' : 'text-muted'" />
          <span class="wp-right-panel__tab-label">{{ tab.label }}</span>
        </button>
      </div>

      <FileExplorer
        v-show="activeTab === 'files'"
        class="wp-right-panel__files"
        :active-path="activePath"
        :open="true"
        :embedded="true"
        :selected-path="selectedFilePath"
        :show-publish="isProjetPluginActive"
        @toggle="emit('toggle')"
        @select-file="onSelectFile"
        @publish-file="onPublishFile"
      />

      <DocumentPreview
        v-show="activeTab === 'preview'"
        :key="previewRefreshKey"
        class="wp-right-panel__preview"
        :relative-path="selectedFilePath"
        :project-path="activePath"
        :workspace-data-dir="workspaceDataDir"
        :show-publish="isProjetPluginActive"
        @publish="onPublishFile"
      />

      <VersionsPanel
        v-show="activeTab === 'preview' && selectedFilePath"
        :relative-path="selectedFilePath"
        :project-path="activePath"
        :workspace-data-dir="workspaceDataDir"
        @restored="onVersionRestored"
      />

      <component
        :is="tab.component"
        v-for="tab in rightPanelPluginTabs"
        :key="tab.key"
        v-show="activeTab === tab.key"
        :ref="(el: unknown) => setPluginRef(tab.pluginId, el)"
        class="wp-right-panel__plugin-pane"
      />

      <PublishToProjectDialog
        v-model:open="publishDialogOpen"
        :source-path="publishSourcePath"
        :workspace-data-dir="workspaceDataDir"
        @published="onPublished"
      />
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import FileExplorer from '@components/workproba/FileExplorer.vue';
import DocumentPreview from '@components/workproba/DocumentPreview.vue';
import VersionsPanel from '@components/workproba/VersionsPanel.vue';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';
import { usePluginSlots } from '@composables/usePluginSlots';
import { usePlugins } from '@composables/usePlugins';

defineProps<{
  activePath: string | null;
  workspaceDataDir?: string | null;
  open: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle'): void;
}>();

const { t } = useI18n();
const { isProjetPluginActive } = usePlugins();
const { rightPanelPluginTabs } = usePluginSlots();

const activeTab = ref<string>('files');
const selectedFilePath = ref<string | null>(null);
const previewRefreshKey = ref(0);
const publishDialogOpen = ref(false);
const publishSourcePath = ref<string | null>(null);
const pluginRefs = new Map<string, { refresh?: () => void | Promise<void> }>();

function setPluginRef(pluginId: string, el: unknown): void {
  if (el) {
    pluginRefs.set(pluginId, el as { refresh?: () => void | Promise<void> });
  } else {
    pluginRefs.delete(pluginId);
  }
}

function onSelectFile(relativePath: string): void {
  selectedFilePath.value = relativePath;
  activeTab.value = 'preview';
}

function onPublishFile(relativePath: string): void {
  publishSourcePath.value = relativePath;
  publishDialogOpen.value = true;
}

function onPublished(): void {
  void pluginRefs.get('workproba.projet')?.refresh?.();
}

function onVersionRestored(): void {
  previewRefreshKey.value += 1;
}

watch(rightPanelPluginTabs, (tabs) => {
  const keys = new Set(['files', 'preview', ...tabs.map((tab) => tab.key)]);
  if (!keys.has(activeTab.value)) {
    activeTab.value = 'files';
  }
});

defineExpose({
  refresh: () => {
    /* délégué via ref sur FileExplorer si besoin futur */
  },
});
</script>

<style scoped lang="scss">
.wp-right-panel {
  flex: none;
  width: 320px;
  min-width: 240px;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  background: var(--wp-surface);
  border-left: 1px solid var(--wp-border);
  transition: width var(--wp-dur) var(--wp-ease);
}

.wp-right-panel--collapsed {
  width: 0;
  min-width: 0;
  border-left: none;
  overflow: hidden;
}

.wp-right-panel__inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 320px;
}

.wp-right-panel__tabs {
  flex: none;
  display: flex;
  border-bottom: 1px solid var(--wp-border);
}

.wp-right-panel__tab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-ui);
  cursor: pointer;
  transition: color var(--wp-dur) var(--wp-ease), border-color var(--wp-dur) var(--wp-ease);

  &:hover {
    color: var(--wp-text);
    background: var(--wp-surface-2);
  }

  &--active {
    color: var(--wp-accent);
    border-bottom-color: var(--wp-accent);
    font-weight: 600;
  }
}

.wp-right-panel__tab-label {
  white-space: nowrap;
}

.wp-right-panel__files,
.wp-right-panel__preview,
.wp-right-panel__plugin-pane {
  flex: 1;
  min-height: 0;
}

.wp-right-panel__preview {
  flex: 1 1 auto;
  min-height: 0;
  max-height: 60%;
}

.wp-right-panel__files {
  width: 100%;
  max-width: none;
  min-width: 0;
  border-left: none;
}
</style>
