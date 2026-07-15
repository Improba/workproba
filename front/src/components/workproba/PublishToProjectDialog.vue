<template>
  <q-dialog :model-value="open" @update:model-value="onOpenChange">
    <div class="publish-dialog">
      <header class="publish-dialog__head">
        <h2 class="publish-dialog__title">{{ t('plugin.workproba.projet.publishTitle') }}</h2>
        <button
          type="button"
          class="publish-dialog__close"
          :aria-label="t('common.close')"
          @click="close"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <p v-if="contentMode" class="publish-dialog__content-hint">
        {{ t('personas.publishToProjectTitle') }}
      </p>
      <p v-else class="publish-dialog__file" :title="sourcePath ?? ''">
        <Lucide name="file-text" size="15" color="text-muted" />
        <span>{{ fileName }}</span>
      </p>

      <div v-if="!projects.length && !loading" class="publish-dialog__onboarding">
        <p>{{ t('plugin.workproba.projet.publishNoProject') }}</p>
        <input
          v-model="newProjectName"
          type="text"
          class="publish-dialog__input"
          :placeholder="t('plugin.workproba.projet.createPlaceholder')"
        />
        <button
          type="button"
          class="publish-dialog__btn"
          :disabled="creating || !newProjectName.trim()"
          @click="onCreateThenPublish"
        >
          {{ t('plugin.workproba.projet.createAndPublish') }}
        </button>
      </div>

      <template v-else>
        <label class="publish-dialog__label" for="publish-project">
          {{ t('plugin.workproba.projet.selectProject') }}
        </label>
        <select
          id="publish-project"
          v-model="selectedProjectId"
          class="publish-dialog__select"
          :disabled="loading"
        >
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>

        <label class="publish-dialog__label" for="publish-name">
          {{ t('plugin.workproba.projet.publishNameLabel') }}
        </label>
        <input
          id="publish-name"
          v-model="documentName"
          type="text"
          class="publish-dialog__input"
          :placeholder="t('plugin.workproba.projet.publishNamePlaceholder')"
        />

        <footer class="publish-dialog__foot">
          <button type="button" class="publish-dialog__btn publish-dialog__btn--ghost" @click="close">
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            class="publish-dialog__btn"
            :disabled="publishing || !canPublish"
            @click="onPublish"
          >
            {{ publishing ? t('common.inProgress') : t('plugin.workproba.projet.publishConfirm') }}
          </button>
        </footer>
      </template>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { PROJET_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import {
  createProjetProject,
  listProjetProjects,
  publishToProjet,
  type ProjetProject,
} from '@services/aiSidecar';

const props = defineProps<{
  open: boolean;
  sourcePath?: string | null;
  content?: string | null;
  defaultName?: string | null;
  workspaceDataDir?: string | null;
}>();

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void;
  (e: 'published'): void;
}>();

const { t } = useI18n();
const { getPluginDataDir } = usePlugins();

const loading = ref(false);
const publishing = ref(false);
const creating = ref(false);
const pluginDataDir = ref<string | null>(null);
const projects = ref<ProjetProject[]>([]);
const selectedProjectId = ref<string | null>(null);
const documentName = ref('');
const newProjectName = ref('');

const fileName = computed(() => {
  if (props.content) return props.defaultName ?? t('personas.publishToProjectTitle');
  if (!props.sourcePath) return '';
  const parts = props.sourcePath.replace(/\\/g, '/').split('/');
  return parts[parts.length - 1] ?? props.sourcePath;
});

const contentMode = computed(() => !!props.content?.trim());

const canPublish = computed(() => {
  if (!props.workspaceDataDir || !selectedProjectId.value || !documentName.value.trim()) {
    return false;
  }
  if (contentMode.value) return !!props.content?.trim();
  return !!props.sourcePath;
});

function close(): void {
  emit('update:open', false);
}

function onOpenChange(v: boolean): void {
  emit('update:open', v);
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
    if (projects.value.length) {
      selectedProjectId.value = projects.value[0].id;
    }
  } finally {
    loading.value = false;
  }
}

async function onPublish(): Promise<void> {
  if (!canPublish.value || !pluginDataDir.value || !props.workspaceDataDir) {
    return;
  }
  publishing.value = true;
  try {
    const result = await publishToProjet({
      pluginDataDir: pluginDataDir.value,
      sourcePath: props.sourcePath ?? undefined,
      content: props.content ?? undefined,
      workspaceDataDir: props.workspaceDataDir,
      projectId: selectedProjectId.value!,
      name: documentName.value.trim(),
    });
    if (!result) {
      Notify.create({
        message: contentMode.value
          ? t('personas.publishToProjectFailed')
          : t('plugin.workproba.projet.publishFailed'),
        color: 'negative',
      });
      return;
    }
    Notify.create({
      message: contentMode.value
        ? t('personas.publishToProjectSuccess', { name: result.name })
        : t('plugin.workproba.projet.publishSuccess', { name: result.name }),
      color: 'positive',
      timeout: 3000,
    });
    emit('published');
    close();
  } finally {
    publishing.value = false;
  }
}

async function onCreateThenPublish(): Promise<void> {
  const name = newProjectName.value.trim();
  if (!name || !pluginDataDir.value || !props.workspaceDataDir) return;
  if (!contentMode.value && !props.sourcePath) return;
  creating.value = true;
  try {
    const project = await createProjetProject(pluginDataDir.value, name);
    if (!project) {
      Notify.create({ message: t('plugin.workproba.projet.createFailed'), color: 'negative' });
      return;
    }
    projects.value = [project];
    selectedProjectId.value = project.id;
    documentName.value = fileName.value;
    newProjectName.value = '';
    await onPublish();
  } finally {
    creating.value = false;
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      documentName.value = props.defaultName ?? fileName.value;
      void loadProjects();
    }
  },
);
</script>

<style scoped lang="scss">
.publish-dialog {
  width: min(420px, 92vw);
  padding: 20px;
  background: var(--wp-surface);
  border-radius: var(--wp-r-md);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
}

.publish-dialog__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.publish-dialog__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--wp-text);
}

.publish-dialog__close {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--wp-r-sm);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.publish-dialog__file {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
  padding: 8px 10px;
  background: var(--wp-surface-2);
  border-radius: var(--wp-r-sm);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
  overflow: hidden;

  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.publish-dialog__content-hint {
  margin: 0 0 16px;
  padding: 8px 10px;
  background: var(--wp-gold-soft);
  border-radius: var(--wp-r-sm);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.publish-dialog__label {
  display: block;
  margin-bottom: 6px;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.publish-dialog__select,
.publish-dialog__input {
  width: 100%;
  margin-bottom: 12px;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-bg);
  color: var(--wp-text);
  font-size: var(--wp-fs-sm);
  font-family: var(--wp-font-ui);
  box-sizing: border-box;
}

.publish-dialog__onboarding {
  display: flex;
  flex-direction: column;
  gap: 10px;

  p {
    margin: 0;
    font-size: var(--wp-fs-sm);
    color: var(--wp-text-muted);
  }
}

.publish-dialog__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.publish-dialog__btn {
  padding: var(--wp-space-2) var(--wp-space-4);
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &--ghost {
    background: transparent;
    border: 1px solid var(--wp-border);
    color: var(--wp-text-muted);
    font-weight: 500;
  }
}
</style>
