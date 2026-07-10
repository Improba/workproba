import { ref, type Ref } from 'vue';
import {
  getActiveProjectPath,
  listLocalDocuments,
  listWorkspaces,
  pickProjectFolder,
  restoreLastProjectPath,
  setActiveProjectPath,
  type LocalDocumentEntry,
  type WorkspaceInfo,
} from './useDesktop';
import { ensureWorkspaceSessions } from '@services/workspaceSession';

const STORAGE_KEY = 'workproba:activeProjectPath';
const WORKSPACE_ID_KEY = 'workproba:activeWorkspaceId';
const WORKSPACE_DATA_DIR_KEY = 'workproba:activeWorkspaceDataDir';

const activePath = ref<string | null>(null);
const activeWorkspaceId = ref<string | null>(null);
const activeDataDir = ref<string | null>(null);
const workspaceTitle = ref<string | null>(null);
const documents = ref<LocalDocumentEntry[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

function persistWorkspaceState(workspace: WorkspaceInfo | null): void {
  if (typeof localStorage === 'undefined') return;

  if (!workspace) {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(WORKSPACE_ID_KEY);
    localStorage.removeItem(WORKSPACE_DATA_DIR_KEY);
    return;
  }

  localStorage.setItem(STORAGE_KEY, workspace.folderPath);
  localStorage.setItem(WORKSPACE_ID_KEY, workspace.id);
  localStorage.setItem(WORKSPACE_DATA_DIR_KEY, workspace.dataDir);
}

function applyWorkspace(workspace: WorkspaceInfo): void {
  activePath.value = workspace.folderPath;
  activeWorkspaceId.value = workspace.id;
  activeDataDir.value = workspace.dataDir;
  workspaceTitle.value = workspace.title;
  persistWorkspaceState(workspace);
}

export interface UseProjectReturn {
  activePath: Ref<string | null>;
  activeWorkspaceId: Ref<string | null>;
  activeDataDir: Ref<string | null>;
  workspaceTitle: Ref<string | null>;
  documents: Ref<LocalDocumentEntry[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  openFolder: () => Promise<void>;
  switchWorkspace: (folderPath: string) => Promise<void>;
  refreshDocuments: () => Promise<void>;
  initFromStoredPath: () => Promise<void>;
}

export function useProject(): UseProjectReturn {
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
        err instanceof Error ? err.message : 'Impossible de lister les documents';
      documents.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function activateWorkspace(workspace: WorkspaceInfo): Promise<void> {
    applyWorkspace(workspace);
    await ensureWorkspaceSessions(workspace.id, workspace.folderPath);
    await refreshDocuments();
  }

  async function openFolder(): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const picked = await pickProjectFolder();
      if (!picked) return;

      const workspace = await setActiveProjectPath(picked);
      await activateWorkspace(workspace);
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : 'Impossible d’ouvrir le dossier';
    } finally {
      loading.value = false;
    }
  }

  async function switchWorkspace(folderPath: string): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const workspace = await setActiveProjectPath(folderPath);
      await activateWorkspace(workspace);
    } catch (err) {
      error.value =
        err instanceof Error ? err.message : 'Impossible de basculer de projet';
    } finally {
      loading.value = false;
    }
  }

  async function initFromStoredPath(): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const restored = await restoreLastProjectPath();
      if (restored) {
        await activateWorkspace(restored);
        return;
      }

      const storedPath =
        typeof localStorage !== 'undefined'
          ? localStorage.getItem(STORAGE_KEY)
          : null;

      const path = storedPath ?? (await getActiveProjectPath());
      if (!path) return;

      const workspace = await setActiveProjectPath(path);
      await activateWorkspace(workspace);
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : 'Impossible de restaurer le projet';
    } finally {
      loading.value = false;
    }
  }

  return {
    activePath,
    activeWorkspaceId,
    activeDataDir,
    workspaceTitle,
    documents,
    loading,
    error,
    openFolder,
    switchWorkspace,
    refreshDocuments,
    initFromStoredPath,
  };
}
