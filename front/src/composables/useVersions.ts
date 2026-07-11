import { ref, type Ref } from 'vue';
import {
  listFileVersions,
  restoreFileVersion,
  type FileVersionEntry,
} from '@services/aiSidecar';

export interface RestoreUndoState {
  filePath: string;
  previousVersionId: string;
}

export interface UseVersionsReturn {
  versions: Ref<FileVersionEntry[]>;
  loading: Ref<boolean>;
  restoring: Ref<boolean>;
  error: Ref<string | null>;
  lastRestore: Ref<RestoreUndoState | null>;
  listVersions: (filePath: string) => Promise<void>;
  restoreVersion: (filePath: string, versionId: string) => Promise<boolean>;
  undoRestore: () => Promise<boolean>;
  clearRestoreBanner: () => void;
}

export function useVersions(
  workspaceDataDir: Ref<string | null | undefined>,
  projectPath: Ref<string | null | undefined>,
): UseVersionsReturn {
  const versions = ref<FileVersionEntry[]>([]);
  const loading = ref(false);
  const restoring = ref(false);
  const error = ref<string | null>(null);
  const lastRestore = ref<RestoreUndoState | null>(null);

  async function listVersionsForFile(filePath: string): Promise<void> {
    const dataDir = workspaceDataDir.value;
    const root = projectPath.value;
    if (!dataDir || !root || !filePath.trim()) {
      versions.value = [];
      return;
    }
    loading.value = true;
    error.value = null;
    try {
      versions.value = await listFileVersions({
        workspaceDataDir: dataDir,
        filePath,
      });
    } catch {
      error.value = 'list_failed';
      versions.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function restoreVersionForFile(
    filePath: string,
    versionId: string,
  ): Promise<boolean> {
    const dataDir = workspaceDataDir.value;
    const root = projectPath.value;
    if (!dataDir || !root || !filePath.trim() || !versionId) return false;

    const currentTop = versions.value[0]?.version_id ?? null;
    restoring.value = true;
    error.value = null;
    try {
      const ok = await restoreFileVersion({
        workspaceDataDir: dataDir,
        projectPath: root,
        filePath,
        versionId,
      });
      if (!ok) {
        error.value = 'restore_failed';
        return false;
      }
      if (currentTop && currentTop !== versionId) {
        lastRestore.value = { filePath, previousVersionId: currentTop };
      } else {
        lastRestore.value = null;
      }
      await listVersionsForFile(filePath);
      return true;
    } catch {
      error.value = 'restore_failed';
      return false;
    } finally {
      restoring.value = false;
    }
  }

  async function undoRestore(): Promise<boolean> {
    const undo = lastRestore.value;
    if (!undo) return false;
    const ok = await restoreVersionForFile(undo.filePath, undo.previousVersionId);
    if (ok) lastRestore.value = null;
    return ok;
  }

  function clearRestoreBanner(): void {
    lastRestore.value = null;
  }

  return {
    versions,
    loading,
    restoring,
    error,
    lastRestore,
    listVersions: listVersionsForFile,
    restoreVersion: restoreVersionForFile,
    undoRestore,
    clearRestoreBanner,
  };
}
