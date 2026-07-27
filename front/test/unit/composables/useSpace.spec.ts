import { beforeEach, describe, expect, it, vi } from 'vitest';

const setActiveProjectPath = vi.fn();
const getWorkspaceInfo = vi.fn();
const listLocalDocuments = vi.fn();
const ensureWorkspaceSessions = vi.fn();

vi.mock('@composables/useDesktop', () => ({
  clearActiveProjectPath: vi.fn(async () => undefined),
  getActiveProjectPath: vi.fn(),
  getWorkspaceInfo: (...args: unknown[]) => getWorkspaceInfo(...args),
  listLocalDocuments: (...args: unknown[]) => listLocalDocuments(...args),
  pickProjectFolder: vi.fn(),
  restoreLastProjectPath: vi.fn(),
  setActiveProjectPath: (...args: unknown[]) => setActiveProjectPath(...args),
  updateWorkspaceTitle: vi.fn(),
}));

vi.mock('@services/workspaceSession', () => ({
  ensureWorkspaceSessions: (...args: unknown[]) => ensureWorkspaceSessions(...args),
}));

vi.mock('@utils/i18nT', () => ({
  t: (key: string) => key,
}));

import { useSpace } from '@composables/useSpace';

const { restoreLastProjectPath, clearActiveProjectPath } = await import('@composables/useDesktop');

const workspace = {
  id: 'ws-1',
  folderPath: '/tmp/projet',
  dataDir: '/data/ws-1',
  title: 'Projet test',
};

describe('useSpace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    listLocalDocuments.mockResolvedValue([]);
    setActiveProjectPath.mockResolvedValue(workspace);
  });

  it('appelle ensureWorkspaceSessions avant applySpace', async () => {
    const callOrder: string[] = [];
    ensureWorkspaceSessions.mockImplementation(async () => {
      callOrder.push('ensure');
      expect(localStorage.getItem('workproba:activeProjectPath')).toBeNull();
    });
    listLocalDocuments.mockImplementation(async () => {
      callOrder.push('refresh');
      expect(localStorage.getItem('workproba:activeProjectPath')).toBe('/tmp/projet');
      return [];
    });

    const { switchSpace, activePath } = useSpace();
    await switchSpace('/tmp/projet');

    expect(callOrder).toEqual(['ensure', 'refresh']);
    expect(activePath.value).toBe('/tmp/projet');
    expect(localStorage.getItem('workproba:activeProjectPath')).toBe('/tmp/projet');
  });

  it('ne persiste pas l espace si ensureWorkspaceSessions échoue', async () => {
    ensureWorkspaceSessions.mockRejectedValue(new Error('ensure_failed'));

    const { switchSpace, activePath } = useSpace();
    activePath.value = null;
    await switchSpace('/tmp/projet');

    expect(activePath.value).toBeNull();
    expect(localStorage.getItem('workproba:activeProjectPath')).toBeNull();
    expect(listLocalDocuments).not.toHaveBeenCalled();
  });

  it('restaure le projet Rust précédent si ensureWorkspaceSessions échoue après set_active', async () => {
    const previousWorkspace = {
      id: 'ws-old',
      folderPath: '/tmp/ancien',
      dataDir: '/data/ws-old',
      title: 'Ancien',
    };
    ensureWorkspaceSessions.mockRejectedValue(new Error('ensure_failed'));
    setActiveProjectPath
      .mockResolvedValueOnce(workspace)
      .mockResolvedValueOnce(previousWorkspace);

    const { switchSpace, activePath } = useSpace();
    activePath.value = previousWorkspace.folderPath;
    localStorage.setItem('workproba:activeProjectPath', previousWorkspace.folderPath);
    localStorage.setItem('workproba:activeWorkspaceId', previousWorkspace.id);
    localStorage.setItem('workproba:activeWorkspaceDataDir', previousWorkspace.dataDir);

    await switchSpace('/tmp/projet');

    expect(setActiveProjectPath).toHaveBeenCalledTimes(2);
    expect(setActiveProjectPath).toHaveBeenNthCalledWith(1, '/tmp/projet');
    expect(setActiveProjectPath).toHaveBeenNthCalledWith(2, '/tmp/ancien');
    expect(activePath.value).toBe('/tmp/ancien');
    expect(localStorage.getItem('workproba:activeProjectPath')).toBe('/tmp/ancien');
    expect(listLocalDocuments).not.toHaveBeenCalled();
  });

  it('nettoie le projet Rust actif si activation échoue sans espace précédent', async () => {
    ensureWorkspaceSessions.mockRejectedValue(new Error('ensure_failed'));

    const { switchSpace, activePath } = useSpace();
    activePath.value = null;
    await switchSpace('/tmp/projet');

    expect(clearActiveProjectPath).toHaveBeenCalledTimes(1);
    expect(setActiveProjectPath).toHaveBeenCalledTimes(1);
  });

  it('ignore un espace archivé en cache local au démarrage', async () => {
    vi.mocked(restoreLastProjectPath).mockResolvedValue(null);
    getWorkspaceInfo.mockResolvedValue({
      ...workspace,
      archived: true,
    });
    localStorage.setItem('workproba:activeProjectPath', '/tmp/projet');

    const { initFromStoredPath, activePath } = useSpace();
    await initFromStoredPath();

    expect(setActiveProjectPath).not.toHaveBeenCalled();
    expect(activePath.value).toBeNull();
    expect(localStorage.getItem('workproba:activeProjectPath')).toBeNull();
  });

  it('ignore un espace archivé renvoyé par restoreLastProjectPath', async () => {
    vi.mocked(restoreLastProjectPath).mockResolvedValue({
      ...workspace,
      archived: true,
    });

    const { initFromStoredPath, activePath } = useSpace();
    await initFromStoredPath();

    expect(setActiveProjectPath).not.toHaveBeenCalled();
    expect(activePath.value).toBeNull();
  });
});
