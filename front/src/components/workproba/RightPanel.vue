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
          v-if="isPersonasPluginActive"
          type="button"
          role="tab"
          class="wp-right-panel__tab wp-right-panel__tab--personas"
          :class="{ 'wp-right-panel__tab--active': activeTab === 'personas' }"
          :aria-selected="activeTab === 'personas'"
          :aria-label="t('personas.panel.title')"
          @click="onPersonasTab"
        >
          <Lucide name="users" size="15" :color="activeTab === 'personas' ? 'wp-gold' : 'text-muted'" />
          <span class="wp-right-panel__tab-label">{{ t('personas.panel.title') }}</span>
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

      <PersonasCentralPanel
        v-if="isPersonasPluginActive"
        v-show="activeTab === 'personas'"
        class="wp-right-panel__personas"
        :plugin-active="isPersonasPluginActive"
        :plugin-data-dir="personasDataDir"
        @ask-opinion="onAskOpinion"
        @meeting="onStartMeeting"
        @discuss="onDiscuss"
        @relaunch-meeting="onRelaunchMeeting"
        @resume-discussion="onResumeDiscussion"
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
import PersonasCentralPanel from '@components/personas/PersonasCentralPanel.vue';
import { usePluginSlots } from '@composables/usePluginSlots';
import { PERSONAS_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { usePersonasActions } from '@composables/usePersonasActions';

defineProps<{
  activePath: string | null;
  workspaceDataDir?: string | null;
  open: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle'): void;
}>();

const { t } = useI18n();
const { isProjetPluginActive, isPersonasPluginActive, getPluginDataDir } = usePlugins();
const { rightPanelPluginTabs } = usePluginSlots();
const {
  askOpinion,
  startMeeting,
  discuss,
  relaunchMeeting,
  resumeDiscussion,
} = usePersonasActions();

const activeTab = ref<string>('files');
const selectedFilePath = ref<string | null>(null);
const previewRefreshKey = ref(0);
const publishDialogOpen = ref(false);
const publishSourcePath = ref<string | null>(null);
const pluginRefs = new Map<string, { refresh?: () => void | Promise<void> }>();
const personasDataDir = ref<string | null>(null);

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

async function ensurePersonasDataDir(): Promise<void> {
  if (personasDataDir.value) return;
  try {
    personasDataDir.value = await getPluginDataDir(PERSONAS_PLUGIN_ID);
  } catch {
    personasDataDir.value = null;
  }
}

watch(
  () => isPersonasPluginActive.value,
  (active) => {
    if (active) void ensurePersonasDataDir();
  },
  { immediate: true },
);

function onPersonasTab(): void {
  activeTab.value = 'personas';
  void ensurePersonasDataDir();
}

function onAskOpinion(personaIds: string[]): void {
  void askOpinion(personaIds);
}

function onStartMeeting(): void {
  void startMeeting();
}

function onDiscuss(personaIds: string[]): void {
  void discuss(personaIds);
}

function onRelaunchMeeting(config: { personaIds: string[]; topic: string; rounds: number }): void {
  void relaunchMeeting(config);
}

function onResumeDiscussion(payload: {
  discussionId: string;
  personaIds: string[];
  messages: import('@composables/usePersonas').DiscussionMessage[];
}): void {
  void resumeDiscussion(payload);
}

watch(rightPanelPluginTabs, (tabs) => {
  const keys = new Set(['files', 'preview', 'personas', ...tabs.map((tab) => tab.key)]);
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
    color: var(--wp-selection);
    border-bottom-color: var(--wp-selection);
    font-weight: 600;
  }
}

.wp-right-panel__tab-label {
  white-space: nowrap;
}

.wp-right-panel__files,
.wp-right-panel__preview,
.wp-right-panel__plugin-pane,
.wp-right-panel__personas {
  flex: 1;
  min-height: 0;
}

.wp-right-panel__personas {
  overflow-y: auto;
}

.wp-right-panel__tab--personas.wp-right-panel__tab--active {
  color: var(--wp-gold);
  border-bottom-color: var(--wp-gold);
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
