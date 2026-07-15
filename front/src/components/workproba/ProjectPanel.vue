<template>
  <div class="project-panel">
    <div v-if="loading" class="project-panel__empty">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="!projects.length" class="project-panel__onboarding">
      <Lucide name="folder-kanban" size="28" color="text-faint" />
      <h3 class="project-panel__onboarding-title">
        {{ t('plugin.workproba.projet.onboardingTitle') }}
      </h3>
      <p class="project-panel__onboarding-text">
        {{ t('plugin.workproba.projet.onboardingText') }}
      </p>
      <div class="project-panel__create">
        <input
          v-model="newProjectName"
          type="text"
          class="project-panel__input"
          :placeholder="t('plugin.workproba.projet.createPlaceholder')"
          @keydown.enter="onCreateProject"
        />
        <button
          type="button"
          class="project-panel__btn"
          :disabled="creating || !newProjectName.trim()"
          @click="onCreateProject"
        >
          {{ t('plugin.workproba.projet.createProject') }}
        </button>
      </div>
    </div>

    <template v-else>
      <div class="project-panel__toolbar">
        <label class="project-panel__label" for="project-select">
          {{ t('plugin.workproba.projet.selectProject') }}
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
          {{ t('plugin.workproba.projet.newProject') }}
        </button>
      </div>

      <div v-if="showCreate" class="project-panel__create project-panel__create--inline">
        <input
          v-model="newProjectName"
          type="text"
          class="project-panel__input"
          :placeholder="t('plugin.workproba.projet.createPlaceholder')"
          @keydown.enter="onCreateProject"
        />
        <button
          type="button"
          class="project-panel__btn"
          :disabled="creating || !newProjectName.trim()"
          @click="onCreateProject"
        >
          {{ t('plugin.workproba.projet.createProject') }}
        </button>
      </div>

      <section class="project-panel__docs">
        <h4 class="project-panel__docs-title">
          {{ t('plugin.workproba.projet.publishedDocuments') }}
        </h4>
        <div v-if="docsLoading" class="project-panel__empty project-panel__empty--small">
          {{ t('common.loading') }}
        </div>
        <p v-else-if="!publishedDocs.length" class="project-panel__empty-text">
          {{ t('plugin.workproba.projet.noPublishedDocuments') }}
        </p>
        <ul v-else class="project-panel__doc-list" role="list">
          <li v-for="doc in publishedDocs" :key="doc.id" class="project-panel__doc">
            <Lucide name="file-check" size="14" color="text-muted" />
            <span class="project-panel__doc-name">{{ doc.name }}</span>
            <span class="project-panel__doc-date">{{ formatDate(doc.created_at) }}</span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { PROJET_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import {
  createProjetProject,
  listProjetProjects,
  listProjetPublishedDocuments,
  type ProjetProject,
  type ProjetPublishedDocument,
} from '@services/aiSidecar';

const { t, locale } = useI18n();
const { getPluginDataDir } = usePlugins();

const loading = ref(true);
const docsLoading = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const newProjectName = ref('');
const pluginDataDir = ref<string | null>(null);
const projects = ref<ProjetProject[]>([]);
const selectedProjectId = ref<string | null>(null);
const publishedDocs = ref<ProjetPublishedDocument[]>([]);

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
  try {
    pluginDataDir.value = await getPluginDataDir(PROJET_PLUGIN_ID);
    if (!pluginDataDir.value) {
      projects.value = [];
      return;
    }
    projects.value = await listProjetProjects(pluginDataDir.value);
    if (projects.value.length && !selectedProjectId.value) {
      selectedProjectId.value = projects.value[0].id;
    }
  } finally {
    loading.value = false;
  }
}

async function loadPublishedDocs(): Promise<void> {
  if (!pluginDataDir.value || !selectedProjectId.value) {
    publishedDocs.value = [];
    return;
  }
  docsLoading.value = true;
  try {
    publishedDocs.value = await listProjetPublishedDocuments(
      pluginDataDir.value,
      selectedProjectId.value,
    );
  } finally {
    docsLoading.value = false;
  }
}

async function onCreateProject(): Promise<void> {
  const name = newProjectName.value.trim();
  if (!name || !pluginDataDir.value) return;
  creating.value = true;
  try {
    const project = await createProjetProject(pluginDataDir.value, name);
    if (!project) {
      Notify.create({ message: t('plugin.workproba.projet.createFailed'), color: 'negative' });
      return;
    }
    projects.value = [...projects.value, project];
    selectedProjectId.value = project.id;
    newProjectName.value = '';
    showCreate.value = false;
    Notify.create({
      message: t('plugin.workproba.projet.createSuccess', { name: project.name }),
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
  await loadProjects();
  await loadPublishedDocs();
});

defineExpose({
  refresh: async () => {
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
  margin: 0 0 var(--wp-space-2);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.project-panel__empty-text {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-faint);
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

.project-panel__doc-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--wp-text);
}

.project-panel__doc-date {
  flex: none;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}
</style>
