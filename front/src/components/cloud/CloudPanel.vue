<template>
  <div class="cloud-panel">
    <div class="cloud-panel__badge">
        {{ t('cloud.experimental') }}
      </div>

      <p v-if="loadError" class="cloud-panel__error" role="alert">
        {{ t('cloud.errorGeneric') }}
      </p>

      <section class="cloud-panel__section">
        <h3 class="cloud-panel__section-title">{{ t('cloud.mountPathTitle') }}</h3>
        <p class="cloud-panel__hint">{{ t('cloud.mountPathHint') }}</p>
        <form class="cloud-panel__config-form" @submit.prevent="onSaveMountPath">
          <input
            v-model="mountPathDraft"
            type="text"
            class="cloud-panel__input"
            :placeholder="t('cloud.mountPathPlaceholder')"
            :disabled="loading || savingConfig"
          />
          <button
            type="button"
            class="cloud-panel__pick-btn"
            :disabled="loading || savingConfig"
            @click="onPickFolder"
          >
            {{ t('cloud.browse') }}
          </button>
          <button
            type="submit"
            class="cloud-panel__save-btn"
            :disabled="loading || savingConfig || !mountPathDraft.trim()"
          >
            {{ t('cloud.saveMountPath') }}
          </button>
        </form>
      </section>

      <section class="cloud-panel__section">
        <h3 class="cloud-panel__section-title">{{ t('cloud.statusTitle') }}</h3>
        <dl class="cloud-panel__status">
          <div>
            <dt>{{ t('cloud.statusConfigured') }}</dt>
            <dd>{{ status?.configured ? t('common.yes') : t('common.no') }}</dd>
          </div>
          <div>
            <dt>{{ t('cloud.statusLastSync') }}</dt>
            <dd>{{ lastSyncLabel }}</dd>
          </div>
          <div>
            <dt>{{ t('cloud.statusSyncedCount') }}</dt>
            <dd>{{ status?.synced_count ?? 0 }}</dd>
          </div>
        </dl>
      </section>

      <section class="cloud-panel__section">
        <div class="cloud-panel__section-head">
          <h3 class="cloud-panel__section-title">{{ t('cloud.projectsTitle') }}</h3>
          <button
            type="button"
            class="cloud-panel__refresh-btn"
            :disabled="loading || syncing"
            @click="refreshProjects"
          >
            {{ t('common.refresh') }}
          </button>
        </div>

        <p v-if="loading && !projects.length" class="cloud-panel__loading">
          {{ t('common.loading') }}
        </p>
        <p v-else-if="!projects.length" class="cloud-panel__empty">
          {{ t('cloud.noProjects') }}
        </p>
        <ul v-else class="cloud-panel__projects" role="list">
          <li v-for="project in projects" :key="project.id" class="cloud-panel__project">
            <span class="cloud-panel__project-name">{{ project.name }}</span>
            <button
              type="button"
              class="cloud-panel__sync-btn"
              :disabled="syncing || !status?.configured"
              @click="onSync(project.id)"
            >
              {{ syncing ? t('cloud.syncing') : t('cloud.syncNow') }}
            </button>
          </li>
        </ul>
      </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import { useCloud } from '@composables/useCloud';
import { PROJET_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { pickProjectFolder } from '@composables/useDesktop';
import {
  listProjetProjects,
  type ProjetProject,
} from '@services/aiSidecar';

const { t } = useI18n();
const { isProjetPluginActive, getPluginDataDir } = usePlugins();
const {
  status,
  loading,
  syncing,
  loadError,
  init,
  refreshStatus,
  configure,
  sync,
} = useCloud();

const mountPathDraft = ref('');
const savingConfig = ref(false);
const projects = ref<ProjetProject[]>([]);

const lastSyncLabel = computed(() => {
  const raw = status.value?.last_sync;
  if (!raw) return t('cloud.neverSynced');
  try {
    return new Date(raw).toLocaleString();
  } catch {
    return raw;
  }
});

async function refreshProjects(): Promise<void> {
  if (!isProjetPluginActive.value) {
    projects.value = [];
    return;
  }
  const dataDir = await getPluginDataDir(PROJET_PLUGIN_ID);
  if (!dataDir) {
    projects.value = [];
    return;
  }
  projects.value = await listProjetProjects(dataDir);
}

async function bootstrap(): Promise<void> {
  await init();
  mountPathDraft.value = status.value?.mount_path ?? '';
  await refreshProjects();
}

async function onPickFolder(): Promise<void> {
  const folder = await pickProjectFolder();
  if (folder) {
    mountPathDraft.value = folder;
  }
}

async function onSaveMountPath(): Promise<void> {
  savingConfig.value = true;
  try {
    const ok = await configure(mountPathDraft.value);
    if (ok) {
      Notify.create({
        message: t('cloud.mountPathSaved'),
        color: 'positive',
        timeout: 2000,
      });
    } else {
      Notify.create({
        message: t('cloud.mountPathSaveFailed'),
        color: 'negative',
      });
    }
  } finally {
    savingConfig.value = false;
  }
}

async function onSync(projectId: string): Promise<void> {
  const synced = await sync(projectId);
  if (synced.length > 0) {
    Notify.create({
      message: t('cloud.syncSuccess', { count: synced.length }),
      color: 'positive',
      timeout: 2500,
    });
  } else if (!loadError.value) {
    Notify.create({
      message: t('cloud.syncEmpty'),
      color: 'info',
      timeout: 2500,
    });
  } else {
    Notify.create({
      message: t('cloud.syncFailed'),
      color: 'negative',
    });
  }
}

watch(isProjetPluginActive, () => {
  void refreshProjects();
});

onMounted(() => {
  void bootstrap();
});

defineExpose({
  refresh: async () => {
    await refreshStatus();
    await refreshProjects();
  },
});
</script>

<style scoped lang="scss">
.cloud-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  min-height: 0;
  overflow-y: auto;
}

.cloud-panel__empty,
.cloud-panel__loading {
  padding: 24px 8px;
  text-align: center;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__badge {
  align-self: flex-start;
  font-size: var(--wp-fs-xs);
  padding: 2px 8px;
  border-radius: var(--wp-r-pill);
  background: var(--wp-gold-soft, var(--wp-surface-3));
  color: var(--wp-gold, var(--wp-text-muted));
  font-weight: 600;
}

.cloud-panel__error {
  margin: 0;
  color: var(--wp-danger);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid var(--wp-border);

  &:first-of-type {
    border-top: none;
    padding-top: 0;
  }
}

.cloud-panel__section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.cloud-panel__section-title {
  margin: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.cloud-panel__hint {
  margin: 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.cloud-panel__config-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cloud-panel__input {
  flex: 1 1 180px;
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  font-size: var(--wp-fs-sm);
}

.cloud-panel__pick-btn,
.cloud-panel__save-btn,
.cloud-panel__refresh-btn,
.cloud-panel__sync-btn {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-xs);
  cursor: pointer;

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.cloud-panel__save-btn {
  color: var(--wp-accent);
  border-color: var(--wp-accent);
}

.cloud-panel__status {
  margin: 0;
  display: grid;
  gap: 8px;
  font-size: var(--wp-fs-xs);

  dt {
    color: var(--wp-text-faint);
  }

  dd {
    margin: 0;
    color: var(--wp-text);
  }
}

.cloud-panel__projects {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cloud-panel__project {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
}

.cloud-panel__project-name {
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
}
</style>
