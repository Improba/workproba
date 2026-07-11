<template>
  <section class="versions-panel" :aria-label="t('shell.versions.titre')">
    <header class="versions-panel__header">
      <h3 class="versions-panel__title">{{ t('shell.versions.titre') }}</h3>
    </header>

    <div v-if="!relativePath" class="versions-panel__empty">
      {{ t('shell.versions.aucuneVersion') }}
    </div>

    <div v-else-if="loading" class="versions-panel__empty">
      {{ t('common.loading') }}
    </div>

    <div v-else-if="!versions.length" class="versions-panel__empty">
      {{ t('shell.versions.aucuneVersion') }}
    </div>

    <ol v-else class="versions-panel__timeline" role="list">
      <li
        v-for="(version, index) in versions"
        :key="version.version_id"
        class="versions-panel__item"
      >
        <div class="versions-panel__marker" aria-hidden="true">
          <span class="versions-panel__dot" :class="{ 'versions-panel__dot--current': index === 0 }" />
          <span v-if="index < versions.length - 1" class="versions-panel__line" />
        </div>
        <div class="versions-panel__content">
          <p class="versions-panel__label">{{ version.label || formatDate(version.created_at) }}</p>
          <p class="versions-panel__meta">
            {{ formatDate(version.created_at) }}
            <span v-if="version.size">{{ t('shell.versions.sizeSep') }}{{ formatSize(version.size) }}</span>
          </p>
          <button
            type="button"
            class="versions-panel__restore"
            :disabled="restoring"
            @click="onRestore(version.version_id)"
          >
            {{ restoring ? t('common.inProgress') : t('shell.versions.restaurer') }}
          </button>
        </div>
      </li>
    </ol>

    <RestoreBanner
      v-if="lastRestore"
      :busy="restoring"
      @undo="onUndo"
      @dismiss="clearRestoreBanner"
    />
  </section>
</template>

<script setup lang="ts">
import { toRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import RestoreBanner from '@components/chat/RestoreBanner.vue';
import { useVersions } from '@composables/useVersions';

const props = defineProps<{
  relativePath: string | null;
  projectPath?: string | null;
  workspaceDataDir?: string | null;
}>();

const emit = defineEmits<{
  restored: [path: string];
}>();

const { t } = useI18n();
const workspaceRef = toRef(props, 'workspaceDataDir');
const projectRef = toRef(props, 'projectPath');
const {
  versions,
  loading,
  restoring,
  lastRestore,
  listVersions,
  restoreVersion,
  undoRestore,
  clearRestoreBanner,
} = useVersions(workspaceRef, projectRef);

function formatDate(iso: string): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

async function onRestore(versionId: string): Promise<void> {
  const path = props.relativePath;
  if (!path) return;
  const confirmed = window.confirm(t('shell.versions.confirmRestaurer'));
  if (!confirmed) return;

  const ok = await restoreVersion(path, versionId);
  if (ok) {
    Notify.create({
      message: t('shell.versions.restauré'),
      color: 'positive',
      timeout: 2500,
    });
    emit('restored', path);
  } else {
    Notify.create({
      message: t('shell.versions.restoreFailed'),
      color: 'negative',
    });
  }
}

async function onUndo(): Promise<void> {
  const ok = await undoRestore();
  if (ok && props.relativePath) {
    emit('restored', props.relativePath);
  }
}

watch(
  () => props.relativePath,
  (path) => {
    clearRestoreBanner();
    if (path) void listVersions(path);
    else versions.value = [];
  },
  { immediate: true },
);

defineExpose({ refresh: () => props.relativePath && listVersions(props.relativePath) });
</script>

<style scoped lang="scss">
.versions-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface-2);
  max-height: 40%;
  min-height: 0;
  overflow: hidden;
}

.versions-panel__header {
  flex: none;
}

.versions-panel__title {
  margin: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 700;
  color: var(--wp-text);
}

.versions-panel__empty {
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  padding: 0.5rem 0;
}

.versions-panel__timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.versions-panel__item {
  display: flex;
  gap: 0.55rem;
}

.versions-panel__marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 0.75rem;
  flex: none;
}

.versions-panel__dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: var(--wp-r-pill);
  background: var(--wp-text-faint);
  margin-top: 0.35rem;

  &--current {
    background: var(--wp-accent);
    box-shadow: 0 0 0 3px var(--wp-accent-soft);
  }
}

.versions-panel__line {
  flex: 1;
  width: 2px;
  min-height: 1.25rem;
  background: var(--wp-border);
  margin: 0.15rem 0;
}

.versions-panel__content {
  flex: 1;
  min-width: 0;
  padding-bottom: 0.65rem;
}

.versions-panel__label {
  margin: 0;
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  color: var(--wp-text);
}

.versions-panel__meta {
  margin: 0.15rem 0 0.35rem;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.versions-panel__restore {
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>
