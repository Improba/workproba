import type {
  AppSettings,
  LlmProviderEntry,
  LlmProviderName,
  LocalDirEntry,
  LocalDocumentEntry,
  WorkspaceInfo,
} from './useDesktop.types';

/** Vrai dans la webview Tauri. */
export function isDesktopApp(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

/** Application bureau uniquement (plus de mode web). */
export function isDesktopMode(): boolean {
  return true;
}

async function tauriInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(command, args);
}

export async function pickProjectFolder(): Promise<string | null> {
  if (!isDesktopApp()) {
    return null;
  }
  return tauriInvoke<string | null>('pick_project_folder');
}

export async function setActiveProjectPath(projectPath: string): Promise<WorkspaceInfo> {
  if (!isDesktopApp()) {
    throw new Error('setActiveProjectPath nécessite l’application bureau Tauri');
  }
  return tauriInvoke<WorkspaceInfo>('set_active_project_path', { projectPath });
}

export async function getActiveProjectPath(): Promise<string | null> {
  if (!isDesktopApp()) return null;
  return tauriInvoke<string | null>('get_active_project_path');
}

export async function getWorkspaceDataDir(projectPath: string): Promise<string | null> {
  if (!isDesktopApp()) return null;
  return tauriInvoke<string | null>('get_workspace_data_dir', { projectPath });
}

export async function restoreLastProjectPath(): Promise<WorkspaceInfo | null> {
  if (!isDesktopApp()) return null;
  return tauriInvoke<WorkspaceInfo | null>('restore_last_project_path');
}

export async function listWorkspaces(): Promise<WorkspaceInfo[]> {
  if (!isDesktopApp()) return [];
  return tauriInvoke<WorkspaceInfo[]>('list_workspaces');
}

export async function listLocalDocuments(
  projectPath: string,
): Promise<LocalDocumentEntry[]> {
  if (!isDesktopApp()) return [];
  return tauriInvoke<LocalDocumentEntry[]>('list_documents', { projectPath });
}

export async function openPath(path: string): Promise<void> {
  if (!isDesktopApp()) {
    return;
  }
  await tauriInvoke<void>('open_path', { path });
}

export async function revealInOs(path: string): Promise<void> {
  if (!isDesktopApp()) return;
  await tauriInvoke<void>('reveal_in_os', { path });
}

export async function listDirEntries(
  projectPath: string,
  dirRelativePath: string,
): Promise<LocalDirEntry[]> {
  if (!isDesktopApp()) return [];
  return tauriInvoke<LocalDirEntry[]>('list_dir_entries', {
    projectPath,
    dirRelativePath,
  });
}

export async function getAppSettings(): Promise<AppSettings> {
  if (!isDesktopApp()) {
    return { version: 1, providers: [] };
  }
  return tauriInvoke<AppSettings>('get_app_settings');
}

export async function saveAppSettings(settings: AppSettings): Promise<AppSettings> {
  if (!isDesktopApp()) {
    throw new Error('saveAppSettings nécessite l’application bureau Tauri');
  }
  return tauriInvoke<AppSettings>('save_app_settings', { settings });
}

export async function openLocalFile(
  filePath: string,
  projectRoot?: string | null,
): Promise<void> {
  if (!isDesktopApp()) return;

  const normalized = filePath.replace(/\\/g, '/');
  const fullPath =
    normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized)
      ? normalized
      : projectRoot
        ? `${projectRoot.replace(/\\/g, '/').replace(/\/$/, '')}/${normalized}`
        : normalized;

  await openPath(fullPath);
}

export type { LocalDirEntry, LocalDocumentEntry, WorkspaceInfo, LlmProviderEntry, LlmProviderName, AppSettings };
