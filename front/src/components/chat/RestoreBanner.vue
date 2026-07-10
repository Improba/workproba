<template>
  <div class="restore-banner" data-testid="restore-banner" role="status">
    <span class="restore-banner__text">Sauvegarde créée.</span>
    <button
      type="button"
      class="restore-banner__action"
      :disabled="restoring"
      aria-label="Restaurer la version précédente du fichier"
      @click="handleRestore"
    >
      {{ restoring ? 'Restauration…' : 'Restaurer' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Notify } from 'quasar';
import { listVersions, restoreVersion } from '@services/versions';

const props = defineProps<{
  projectPath: string;
  sessionId: string;
  filePath: string;
  snapshotPath?: string;
}>();

const emit = defineEmits<{
  restored: [path: string];
}>();

const restoring = ref(false);

async function handleRestore(): Promise<void> {
  if (restoring.value) return;
  restoring.value = true;

  try {
    let snapshotPath = props.snapshotPath;
    if (!snapshotPath) {
      const snapshots = await listVersions(
        props.projectPath,
        props.sessionId,
        props.filePath,
      );
      const latest = snapshots[snapshots.length - 1];
      if (!latest?.snapshot_path) {
        throw new Error('Aucune sauvegarde disponible');
      }
      snapshotPath = latest.snapshot_path;
    }

    const result = await restoreVersion(
      props.projectPath,
      props.sessionId,
      snapshotPath,
    );
    Notify.create({
      message: 'Version restaurée',
      classes: 'bg-positive text-neutral-lowest',
    });
    emit('restored', result.restored_path);
  } catch {
    Notify.create({
      message: 'Impossible de restaurer cette version',
      classes: 'bg-danger text-neutral-lowest',
    });
  } finally {
    restoring.value = false;
  }
}
</script>

<style scoped lang="scss">
.restore-banner {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.45rem 0.65rem;
  margin-top: 0.45rem;
  padding: 0.45rem 0.65rem;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  border: 1px solid var(--wp-border);
  font-size: var(--wp-fs-sm);
  color: var(--wp-text-muted);
}

.restore-banner__text {
  flex: 1 1 auto;
  min-width: 0;
}

.restore-banner__action {
  flex: 0 0 auto;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface);
  color: var(--wp-accent-strong);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;
  transition: background var(--wp-dur) var(--wp-ease);

  &:focus-visible {
    outline: 2px solid var(--wp-focus-ring);
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }

  &:not(:disabled):hover {
    background: var(--wp-accent-soft);
  }
}
</style>
