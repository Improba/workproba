import { ref, type Ref } from 'vue';
import {
  getActiveProjectPath,
  listLocalDocuments,
  pickProjectFolder,
  restoreLastProjectPath,
  setActiveProjectPath,
  updateWorkspaceTitle,
  type LocalDocumentEntry,
  type WorkspaceInfo,
} from './useDesktop';
import { ensureWorkspaceSessions } from '@services/workspaceSession';
import { t } from '@utils/i18nT';

const STORAGE_KEY = 'workproba:activeProjectPath';
const SPACE_ID_KEY = 'workproba:activeWorkspaceId';
const SPACE_DATA_DIR_KEY = 'workproba:activeWorkspaceDataDir';

const activePath = ref<string | null>(null);
const activeSpaceId = ref<string | null>(null);
const activeDataDir = ref<string | null>(null);
const spaceTitle = ref<string | null>(null);
const documents = ref<LocalDocumentEntry[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

function persistSpaceState(workspace: WorkspaceInfo | null): void {
  if (typeof localStorage === 'undefined') return;

  if (!workspace) {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(SPACE_ID_KEY);
    localStorage.removeItem(SPACE_DATA_DIR_KEY);
    return;
  }

  localStorage.setItem(STORAGE_KEY, workspace.folderPath);
  localStorage.setItem(SPACE_ID_KEY, workspace.id);
  localStorage.setItem(SPACE_DATA_DIR_KEY, workspace.dataDir);
}

function applySpace(workspace: WorkspaceInfo): void {
  activePath.value = workspace.folderPath;
  activeSpaceId.value = workspace.id;
  activeDataDir.value = workspace.dataDir;
  spaceTitle.value = workspace.title;
  persistSpaceState(workspace);
}

/**
 * Best-effort rollback when `set_active_project_path` succeeded but front activation failed.
 * No Rust command clears the active project; re-activate the previous path when known.
 */
async function rollbackRustActiveProject(previousPath: string | null): Promise<void> {
  if (!previousPath) {
    // TODO: no IPC to clear Rust active project when there was no prior space.
    return;
  }
  try {
    await setActiveProjectPath(previousPath);
  } catch {
    // Front state is already unchanged; Rust may stay on the failed activation.
  }
}

export interface UseSpaceReturn {
  activePath: Ref<string | null>;
  activeSpaceId: Ref<string | null>;
  activeDataDir: Ref<string | null>;
  spaceTitle: Ref<string | null>;
  documents: Ref<LocalDocumentEntry[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  openSpace: () => Promise<void>;
  switchSpace: (folderPath: string) => Promise<void>;
  renameSpace: (spaceId: string, title: string) => Promise<WorkspaceInfo>;
  refreshDocuments: () => Promise<void>;
  initFromStoredPath: () => Promise<void>;
}

export function useSpace(): UseSpaceReturn {
  async function refreshDocuments(): Promise<void> {
    if (!activePath.value) {
      documents.value = [];
      return;
    }

    loading.value = true;
    error.value = null;

    try {
      documents.value = await listLocalDocuments(activePath.value);
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : t('errors.listDocumentsFailed');
      documents.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function activateSpace(workspace: WorkspaceInfo): Promise<void> {
    await ensureWorkspaceSessions(workspace.id, workspace.folderPath);
    applySpace(workspace);
    await refreshDocuments();
  }

  async function openSpace(): Promise<void> {
    loading.value = true;
    error.value = null;
    const previousPath = activePath.value;

    try {
      const picked = await pickProjectFolder();
      if (!picked) return;

      const workspace = await setActiveProjectPath(picked);
      try {
        await activateSpace(workspace);
      } catch (err) {
        await rollbackRustActiveProject(previousPath);
        throw err;
      }
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : t('errors.openSpaceFailed');
    } finally {
      loading.value = false;
    }
  }

  async function switchSpace(folderPath: string): Promise<void> {
    loading.value = true;
    error.value = null;
    const previousPath = activePath.value;
    try {
      const workspace = await setActiveProjectPath(folderPath);
      try {
        await activateSpace(workspace);
      } catch (err) {
        await rollbackRustActiveProject(previousPath);
        throw err;
      }
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : t('errors.switchSpaceFailed');
    } finally {
      loading.value = false;
    }
  }

  async function renameSpace(spaceId: string, title: string): Promise<WorkspaceInfo> {
    const updated = await updateWorkspaceTitle(spaceId, title);
    if (activeSpaceId.value === spaceId) {
      spaceTitle.value = updated.title;
    }
    return updated;
  }

  async function initFromStoredPath(): Promise<void> {
    loading.value = true;
    error.value = null;
    const previousPath = activePath.value;

    try {
      const restored = await restoreLastProjectPath();
      if (restored) {
        try {
          await activateSpace(restored);
        } catch (err) {
          await rollbackRustActiveProject(previousPath);
          throw err;
        }
        return;
      }

      const storedPath =
        typeof localStorage !== 'undefined'
          ? localStorage.getItem(STORAGE_KEY)
          : null;

      const path = storedPath ?? (await getActiveProjectPath());
      if (!path) return;

      const workspace = await setActiveProjectPath(path);
      try {
        await activateSpace(workspace);
      } catch (err) {
        await rollbackRustActiveProject(previousPath);
        throw err;
      }
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : t('errors.restoreSpaceFailed');
    } finally {
      loading.value = false;
    }
  }

  return {
    activePath,
    activeSpaceId,
    activeDataDir,
    spaceTitle,
    documents,
    loading,
    error,
    openSpace,
    switchSpace,
    renameSpace,
    refreshDocuments,
    initFromStoredPath,
  };
}
