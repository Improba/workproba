<template>
  <div class="project-panel">
    <div v-if="loading" class="project-panel__empty">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="!projects.length" class="project-panel__onboarding">
      <Lucide name="folder-kanban" size="28" color="text-faint" />
      <h3 class="project-panel__onboarding-title">
        {{ t(projetKey('onboardingTitle')) }}
      </h3>
      <p class="project-panel__onboarding-text">
        {{ t(projetKey('onboardingText')) }}
      </p>
      <div class="project-panel__create">
        <input
          v-model="newProjectName"
          type="text"
          class="project-panel__input"
          :placeholder="t(projetKey('createPlaceholder'))"
          @keydown.enter="onCreateProject"
        />
        <button
          type="button"
          class="project-panel__btn"
          :disabled="creating || !newProjectName.trim()"
          @click="onCreateProject"
        >
          {{ t(projetKey('createProject')) }}
        </button>
      </div>
    </div>

    <template v-else>
      <div class="project-panel__toolbar">
        <label class="project-panel__label" for="project-select">
          {{ t(projetKey('selectProject')) }}
        </label>
        <select
          id="project-select"
          v-model="selectedProjectId"
          class="project-panel__select"
        >
          <option v-for="p in projects" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
        <button
          type="button"
          class="project-panel__btn project-panel__btn--ghost"
          @click="showCreate = !showCreate"
        >
          {{ t(projetKey('newProject')) }}
        </button>
      </div>

      <div v-if="showCreate" class="project-panel__create project-panel__create--inline">
        <input
          v-model="newProjectName"
          type="text"
          class="project-panel__input"
          :placeholder="t(projetKey('createPlaceholder'))"
          @keydown.enter="onCreateProject"
        />
        <button
          type="button"
          class="project-panel__btn"
          :disabled="creating || !newProjectName.trim()"
          @click="onCreateProject"
        >
          {{ t(projetKey('createProject')) }}
        </button>
      </div>

      <section class="project-panel__docs">
        <h4 class="project-panel__docs-title">
          {{ t(isEnrolled ? 'plugin.workproba.projet.publishedDocumentsShared' : 'plugin.workproba.projet.publishedDocuments') }}
        </h4>
        <p class="project-panel__scope-hint">
          {{ t(isEnrolled ? 'plugin.workproba.projet.scopeHintShared' : 'plugin.workproba.projet.scopeHintLocal') }}
        </p>
        <div v-if="docsLoading" class="project-panel__empty project-panel__empty--small">
          {{ t('common.loading') }}
        </div>
        <p v-else-if="loadError" class="project-panel__empty-text project-panel__empty-text--error" role="alert">
          {{ loadError }}
        </p>
        <p v-else-if="!publishedDocs.length" class="project-panel__empty-text">
          {{ t(projetKey('noPublishedDocuments')) }}
        </p>
        <ul v-else class="project-panel__doc-list" role="list">
          <li
            v-for="doc in publishedDocs"
            :key="doc.id"
            class="project-panel__doc"
            :class="{
              'project-panel__doc--clickable': isEnrolled,
              'project-panel__doc--opening': openingDocId === doc.id,
            }"
            @click="isEnrolled ? onOpenCloudDoc(doc) : undefined"
          >
            <Lucide name="file-check" size="14" color="text-muted" />
            <span class="project-panel__doc-name">{{ doc.name }}</span>
            <span v-if="doc.version" class="project-panel__doc-version">v{{ doc.version }}</span>
            <div v-if="isEnrolled" class="project-panel__badges">
              <span
                v-if="doc.cloud_confirmed === true"
                class="project-panel__badge project-panel__badge--cloud"
              >
                {{ t('plugin.workproba.projet.syncStatusCloud') }}
              </span>
              <span
                v-else-if="doc.cloud_pending"
                class="project-panel__badge project-panel__badge--pending"
              >
                {{ t('plugin.workproba.projet.syncStatusCloudPending') }}
              </span>
            </div>
            <div v-else-if="syncByDocId[doc.id]" class="project-panel__badges">
              <span
                v-if="syncByDocId[doc.id]?.published"
                class="project-panel__badge project-panel__badge--published"
              >
                {{ t('plugin.workproba.projet.syncStatusPublished') }}
              </span>
              <span
                v-if="syncByDocId[doc.id]?.mount_synced"
                class="project-panel__badge project-panel__badge--mount"
              >
                {{ t('plugin.workproba.projet.syncStatusMount') }}
              </span>
              <span
                v-if="syncByDocId[doc.id]?.cloud_confirmed"
                class="project-panel__badge project-panel__badge--cloud"
              >
                {{ t('plugin.workproba.projet.syncStatusCloud') }}
              </span>
              <span
                v-else-if="syncByDocId[doc.id]?.cloud_pending"
                class="project-panel__badge project-panel__badge--pending"
              >
                {{ t('plugin.workproba.projet.syncStatusCloudPending') }}
              </span>
            </div>
            <span class="project-panel__doc-date">{{ formatDate(doc.created_at) }}</span>
            <button
              v-if="isEnrolled && doc.has_local_cache"
              type="button"
              class="project-panel__btn project-panel__btn--ghost project-panel__republish"
              :disabled="republishingDocId === doc.id"
              @click.stop="onRepublishCloudDoc(doc)"
            >
              {{ t('cloud.republishToCloud') }}
            </button>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { CLOUD_PLUGIN_ID, PROJET_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { openPath } from '@composables/useDesktop';
import { useCloud } from '@composables/useCloud';
import {
  createProjetProject,
  listCloudArtefacts,
  listProjetArtefactSyncStatus,
  listProjetProjects,
  listProjetPublishedDocuments,
  openCloudArtefact,
  republishCloudArtefact,
  type ProjetArtefactSyncStatus,
  type ProjetProject,
  type ProjetPublishedDocument,
} from '@services/aiSidecar';

const { t, locale } = useI18n();
const { getPluginDataDir } = usePlugins();
const { status, isEnrolled, init: initCloud, refreshStatus } = useCloud();

function projetKey(base: string): string {
  return isEnrolled.value
    ? `plugin.workproba.projet.${base}Shared`
    : `plugin.workproba.projet.${base}`;
}

const loading = ref(true);
const docsLoading = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const newProjectName = ref('');
const loadError = ref<string | null>(null);
const pluginDataDir = ref<string | null>(null);
const cloudPluginDataDir = ref<string | null>(null);
const projects = ref<ProjetProject[]>([]);
const selectedProjectId = ref<string | null>(null);
const publishedDocs = ref<ProjetPublishedDocument[]>([]);
const syncStatuses = ref<ProjetArtefactSyncStatus[]>([]);
const openingDocId = ref<string | null>(null);
const republishingDocId = ref<string | null>(null);

const syncByDocId = computed(() =>
  Object.fromEntries(syncStatuses.value.map((item) => [item.id, item])),
);

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

async function loadProjects(): Promise<void> {
  loading.value = true;
  loadError.value = null;
  try {
    pluginDataDir.value = await getPluginDataDir(PROJET_PLUGIN_ID);
    cloudPluginDataDir.value = await getPluginDataDir(CLOUD_PLUGIN_ID);
    if (!pluginDataDir.value) {
      projects.value = [];
      return;
    }
    const result = await listProjetProjects(pluginDataDir.value);
    if (!result.ok) {
      projects.value = [];
      loadError.value = result.error;
      return;
    }
    projects.value = result.data;
    if (projects.value.length && !selectedProjectId.value) {
      selectedProjectId.value = projects.value[0].id;
    }
  } finally {
    loading.value = false;
  }
}

async function loadPublishedDocs(): Promise<void> {
  if (!selectedProjectId.value) {
    publishedDocs.value = [];
    syncStatuses.value = [];
    return;
  }
  docsLoading.value = true;
  loadError.value = null;
  try {
    await refreshStatus();
    if (status.value?.enrolled) {
      if (!cloudPluginDataDir.value) {
        publishedDocs.value = [];
        syncStatuses.value = [];
        return;
      }
      const docsResult = await listCloudArtefacts(
        cloudPluginDataDir.value,
        selectedProjectId.value,
      );
      if (!docsResult.ok) {
        publishedDocs.value = [];
        loadError.value = docsResult.error;
        syncStatuses.value = [];
        return;
      }
      publishedDocs.value = docsResult.data;
      syncStatuses.value = [];
      return;
    }

    if (!pluginDataDir.value) {
      publishedDocs.value = [];
      syncStatuses.value = [];
      return;
    }
    const [docsResult, syncResult] = await Promise.all([
      listProjetPublishedDocuments(pluginDataDir.value, selectedProjectId.value),
      listProjetArtefactSyncStatus({
        pluginDataDir: pluginDataDir.value,
        projectId: selectedProjectId.value,
        cloudPluginDataDir: cloudPluginDataDir.value ?? undefined,
      }),
    ]);
    if (!docsResult.ok) {
      publishedDocs.value = [];
      loadError.value = docsResult.error;
      syncStatuses.value = syncResult.ok ? syncResult.data : [];
      return;
    }
    publishedDocs.value = docsResult.data;
    syncStatuses.value = syncResult.ok ? syncResult.data : [];
    if (!syncResult.ok && !loadError.value) {
      loadError.value = syncResult.error;
    }
  } finally {
    docsLoading.value = false;
  }
}

async function onOpenCloudDoc(doc: ProjetPublishedDocument): Promise<void> {
  if (!isEnrolled.value || !cloudPluginDataDir.value || !selectedProjectId.value) return;
  if (openingDocId.value) return;
  openingDocId.value = doc.id;
  try {
    const result = await openCloudArtefact({
      pluginDataDir: cloudPluginDataDir.value,
      projectId: selectedProjectId.value,
      artefactId: doc.id,
    });
    if (!result.ok) {
      Notify.create({
        message: result.error || t('cloud.openFailed'),
        color: 'negative',
      });
      return;
    }
    try {
      await openPath(result.data.local_path);
    } catch {
      Notify.create({
        message: t('cloud.cachedAt', { path: result.data.local_path }),
        color: 'info',
        timeout: 5000,
      });
    }
    Notify.create({
      message: t('cloud.republishHint'),
      color: 'info',
      timeout: 6000,
    });
    publishedDocs.value = publishedDocs.value.map((item) =>
      item.id === doc.id ? { ...item, has_local_cache: true } : item,
    );
  } finally {
    openingDocId.value = null;
  }
}

async function onRepublishCloudDoc(doc: ProjetPublishedDocument): Promise<void> {
  if (!isEnrolled.value || !cloudPluginDataDir.value || !selectedProjectId.value) return;
  if (republishingDocId.value) return;
  republishingDocId.value = doc.id;
  try {
    const result = await republishCloudArtefact({
      pluginDataDir: cloudPluginDataDir.value,
      projectId: selectedProjectId.value,
      artefactId: doc.id,
    });
    if (!result.ok) {
      Notify.create({
        message: result.error || t('cloud.republishFailed'),
        color: 'negative',
      });
      return;
    }
    publishedDocs.value = publishedDocs.value.map((item) =>
      item.id === doc.id
        ? { ...result.data, has_local_cache: true }
        : item,
    );
    Notify.create({
      message: t('cloud.republishSuccess', {
        name: doc.name,
        version: result.data.version ?? '',
      }),
      color: 'positive',
      timeout: 3000,
    });
  } finally {
    republishingDocId.value = null;
  }
}

async function onCreateProject(): Promise<void> {
  const name = newProjectName.value.trim();
  if (!name || !pluginDataDir.value) return;
  creating.value = true;
  try {
    const result = await createProjetProject(pluginDataDir.value, name);
    if (!result.ok) {
      Notify.create({
        message: result.error || t('plugin.workproba.projet.createFailed'),
        color: 'negative',
      });
      return;
    }
    const project = result.data;
    projects.value = [...projects.value, project];
    selectedProjectId.value = project.id;
    newProjectName.value = '';
    showCreate.value = false;
    Notify.create({
      message: t(projetKey('createSuccess'), { name: project.name }),
      color: 'positive',
      timeout: 2000,
    });
  } finally {
    creating.value = false;
  }
}

watch(selectedProjectId, () => {
  void loadPublishedDocs();
});

onMounted(async () => {
  await initCloud();
  await loadProjects();
  await loadPublishedDocs();
});

defineExpose({
  refresh: async () => {
    await refreshStatus();
    await loadProjects();
    await loadPublishedDocs();
  },
});
</script>

<style scoped lang="scss">
.project-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--wp-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-3);
}

.project-panel__empty {
  padding: var(--wp-space-6);
  text-align: center;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);

  &--small {
    padding: var(--wp-space-3);
  }
}

.project-panel__onboarding {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--wp-space-6);
  gap: var(--wp-space-3);
}

.project-panel__onboarding-title {
  margin: 0;
  font-size: var(--wp-fs-md);
  font-weight: 600;
  color: var(--wp-text);
}

.project-panel__onboarding-text {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  max-width: 28ch;
  line-height: var(--wp-lh-relaxed);
}

.project-panel__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--wp-space-2);
}

.project-panel__label {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  width: 100%;
}

.project-panel__select {
  flex: 1;
  min-width: 120px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-family: var(--wp-font-ui);
}

.project-panel__create {
  display: flex;
  gap: var(--wp-space-2);

  &--inline {
    padding-top: var(--wp-space-1);
  }
}

.project-panel__input {
  flex: 1;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-family: var(--wp-font-ui);
}

.project-panel__btn {
  padding: var(--wp-space-2) var(--wp-space-3);
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &--ghost {
    background: transparent;
    border: 1px solid var(--wp-border);
    color: var(--wp-text-muted);
  }
}

.project-panel__docs-title {
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.project-panel__scope-hint {
  margin: 0 0 var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
  line-height: var(--wp-lh-relaxed);
}

.project-panel__empty-text {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-faint);

  &--error {
    color: var(--wp-danger);
  }
}

.project-panel__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  flex: none;
}

.project-panel__badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--wp-r-pill);
  white-space: nowrap;

  &--published {
    background: var(--wp-surface-3);
    color: var(--wp-text-muted);
  }

  &--mount {
    background: var(--wp-accent-soft, var(--wp-surface-3));
    color: var(--wp-accent);
  }

  &--cloud {
    background: color-mix(in srgb, var(--wp-positive, #2e7d32) 15%, transparent);
    color: var(--wp-positive, #2e7d32);
  }

  &--pending {
    background: var(--wp-gold-soft, var(--wp-surface-3));
    color: var(--wp-gold, var(--wp-text-muted));
  }
}

.project-panel__doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.project-panel__doc {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-sm);
}

.project-panel__doc--clickable {
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-3);
  }
}

.project-panel__doc--opening {
  opacity: 0.7;
  pointer-events: none;
}

.project-panel__doc-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--wp-text);
}

.project-panel__doc-version {
  flex: none;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.project-panel__doc-date {
  flex: none;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.project-panel__republish {
  flex: none;
  font-size: 10px;
  padding: 2px 8px;
}
</style>
