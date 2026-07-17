import { beforeEach, describe, expect, it, vi } from 'vitest';

const setActiveProjectPath = vi.fn();
const listLocalDocuments = vi.fn();
const ensureWorkspaceSessions = vi.fn();

vi.mock('@composables/useDesktop', () => ({
  getActiveProjectPath: vi.fn(),
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
});
