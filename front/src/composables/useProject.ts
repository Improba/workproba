import type { Ref } from 'vue';
import {
  useSpace,
  type UseSpaceReturn,
} from './useSpace';
import type { LocalDocumentEntry, WorkspaceInfo } from './useDesktop';

/** @deprecated Préférez `useSpace`. Conservé pour compatibilité ascendante. */
export interface UseProjectReturn {
  activePath: Ref<string | null>;
  activeWorkspaceId: Ref<string | null>;
  activeDataDir: Ref<string | null>;
  workspaceTitle: Ref<string | null>;
  documents: Ref<LocalDocumentEntry[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  openSpace: () => Promise<void>;
  switchWorkspace: (folderPath: string) => Promise<void>;
  renameSpace: (workspaceId: string, title: string) => Promise<WorkspaceInfo>;
  refreshDocuments: () => Promise<void>;
  initFromStoredPath: () => Promise<void>;
}

/** @deprecated Préférez `useSpace`. Délègue au composable espace. */
export function useProject(): UseProjectReturn {
  const space: UseSpaceReturn = useSpace();
  return {
    activePath: space.activePath,
    activeWorkspaceId: space.activeSpaceId,
    activeDataDir: space.activeDataDir,
    workspaceTitle: space.spaceTitle,
    documents: space.documents,
    loading: space.loading,
    error: space.error,
    openSpace: space.openSpace,
    switchWorkspace: space.switchSpace,
    renameSpace: space.renameSpace,
    refreshDocuments: space.refreshDocuments,
    initFromStoredPath: space.initFromStoredPath,
  };
}
