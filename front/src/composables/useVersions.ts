import { ref, type Ref } from 'vue';
import {
  listFileVersions,
  purgeFileVersions,
  restoreFileVersion,
  type FileVersionEntry,
} from '@services/aiSidecar';

export interface RestoreUndoState {
  filePath: string;
  previousVersionId: string;
}

export interface PendingRestoreState {
  filePath: string;
  versionId: string;
  entry: FileVersionEntry;
}

export interface PurgeVersionsResult {
  ok: boolean;
  versionsRemoved: number;
}

export interface UseVersionsReturn {
  versions: Ref<FileVersionEntry[]>;
  loading: Ref<boolean>;
  restoring: Ref<boolean>;
  purging: Ref<boolean>;
  error: Ref<string | null>;
  lastRestore: Ref<RestoreUndoState | null>;
  pendingRestore: Ref<PendingRestoreState | null>;
  listVersions: (filePath: string) => Promise<void>;
  openRestoreConfirm: (filePath: string, versionId: string) => void;
  closeRestoreConfirm: () => void;
  restoreVersion: (filePath: string, versionId: string) => Promise<boolean>;
  purgeVersions: (filePath: string, opts?: { keepLast?: number; olderThanDays?: number }) => Promise<PurgeVersionsResult>;
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
  const purging = ref(false);
  const error = ref<string | null>(null);
  const lastRestore = ref<RestoreUndoState | null>(null);
  const pendingRestore = ref<PendingRestoreState | null>(null);

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

  function openRestoreConfirm(filePath: string, versionId: string): void {
    const entry = versions.value.find((item) => item.version_id === versionId);
    if (!entry || !filePath.trim()) return;
    pendingRestore.value = { filePath, versionId, entry };
  }

  function closeRestoreConfirm(): void {
    pendingRestore.value = null;
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

  async function purgeVersionsForFile(
    filePath: string,
    opts?: { keepLast?: number; olderThanDays?: number },
  ): Promise<PurgeVersionsResult> {
    const dataDir = workspaceDataDir.value;
    if (!dataDir || !filePath.trim()) {
      return { ok: false, versionsRemoved: 0 };
    }
    purging.value = true;
    error.value = null;
    try {
      const result = await purgeFileVersions({
        workspaceDataDir: dataDir,
        filePath,
        keepLast: opts?.keepLast,
        olderThanDays: opts?.olderThanDays,
      });
      if (!result.ok) {
        error.value = 'purge_failed';
        return { ok: false, versionsRemoved: 0 };
      }
      await listVersionsForFile(filePath);
      return { ok: true, versionsRemoved: result.versionsRemoved };
    } catch {
      error.value = 'purge_failed';
      return { ok: false, versionsRemoved: 0 };
    } finally {
      purging.value = false;
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
    purging,
    error,
    lastRestore,
    pendingRestore,
    listVersions: listVersionsForFile,
    openRestoreConfirm,
    closeRestoreConfirm,
    restoreVersion: restoreVersionForFile,
    purgeVersions: purgeVersionsForFile,
    undoRestore,
    clearRestoreBanner,
  };
}
