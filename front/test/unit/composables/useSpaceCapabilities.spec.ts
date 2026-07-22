import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';

const activeDataDir = ref<string | null>('/tmp/ws');
const activePluginIds = ref<string[]>(['workproba.cloud', 'workproba.projet']);
const getPluginDataDir = vi.fn(async () => '/tmp/plugins/cloud');

const fetchWorkspaceCapabilities = vi.fn();
const updateWorkspaceCapabilitiesWanted = vi.fn();

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({ activeDataDir }),
}));

vi.mock('@composables/usePlugins', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@composables/usePlugins')>();
  return {
    ...actual,
    usePlugins: () => ({
      activePluginIds,
      getPluginDataDir,
    }),
  };
});

vi.mock('@services/aiSidecar', () => ({
  fetchWorkspaceCapabilities: (...args: unknown[]) => fetchWorkspaceCapabilities(...args),
  updateWorkspaceCapabilitiesWanted: (...args: unknown[]) =>
    updateWorkspaceCapabilitiesWanted(...args),
}));

import { useSpaceCapabilities } from '@composables/useSpaceCapabilities';

describe('useSpaceCapabilities', () => {
  beforeEach(() => {
    activeDataDir.value = '/tmp/ws';
    fetchWorkspaceCapabilities.mockReset();
    updateWorkspaceCapabilitiesWanted.mockReset();
    fetchWorkspaceCapabilities.mockResolvedValue({
      ok: true,
      data: {
        wanted: {
          workproba_cloud: false,
          projects: false,
          regards: true,
        },
        items: [
          {
            id: 'workproba_cloud',
            status: 'available',
            wanted: false,
            entitled: true,
          },
          {
            id: 'projects',
            status: 'unavailable',
            wanted: false,
            entitled: true,
            unavailableReason: 'parent_cloud_off',
          },
          {
            id: 'regards',
            status: 'active',
            wanted: true,
            entitled: true,
          },
          {
            id: 'managed:ihora',
            status: 'unavailable',
            wanted: true,
            entitled: true,
            unavailableReason: 'parent_cloud_off',
          },
        ],
        effectiveIds: ['regards'],
        cloudWanted: false,
        cloudEntitled: true,
      },
    });
  });

  it('classe les items en actives / disponibles / indisponibles (managed first)', async () => {
    const {
      refresh,
      activeItems,
      availableItems,
      unavailableItems,
    } = useSpaceCapabilities();
    await refresh();

    expect(activeItems.value.map((i) => i.id)).toEqual(['regards']);
    expect(availableItems.value.map((i) => i.id)).toEqual(['workproba_cloud']);
    expect(unavailableItems.value.map((i) => i.id)).toEqual([
      'managed:ihora',
      'projects',
    ]);
  });

  it('signale autoWantedCloud quand un nested est activé sans cloud', async () => {
    updateWorkspaceCapabilitiesWanted.mockResolvedValue({
      ok: true,
      data: {
        wanted: {
          workproba_cloud: true,
          projects: true,
          regards: true,
        },
        items: [],
        effectiveIds: ['workproba_cloud', 'projects', 'regards'],
        cloudWanted: true,
        cloudEntitled: true,
      },
    });

    const { refresh, setWanted } = useSpaceCapabilities();
    await refresh();
    const result = await setWanted('projects', true);

    expect(result.ok).toBe(true);
    expect(result.autoWantedCloud).toBe(true);
    expect(updateWorkspaceCapabilitiesWanted).toHaveBeenCalledWith(
      expect.objectContaining({
        wanted: { projects: true },
      }),
    );
  });

  it('utilise workspaceDataDir fourni au lieu de activeDataDir', async () => {
    activeDataDir.value = '/tmp/active-ws';
    const customDir = ref('/tmp/custom-ws');
    fetchWorkspaceCapabilities.mockClear();
    const { refresh } = useSpaceCapabilities({ workspaceDataDir: customDir });
    await refresh();

    expect(fetchWorkspaceCapabilities).toHaveBeenCalledWith(
      expect.objectContaining({ workspaceDataDir: '/tmp/custom-ws' }),
    );

    activeDataDir.value = '/tmp/other-ws';
    fetchWorkspaceCapabilities.mockClear();
    await refresh();
    expect(fetchWorkspaceCapabilities).toHaveBeenCalledWith(
      expect.objectContaining({ workspaceDataDir: '/tmp/custom-ws' }),
    );

    customDir.value = '/tmp/updated-custom';
    await refresh();
    expect(fetchWorkspaceCapabilities).toHaveBeenLastCalledWith(
      expect.objectContaining({ workspaceDataDir: '/tmp/updated-custom' }),
    );
  });

  it('ignore un dataDir vide ou blanc', async () => {
    const blankDir = ref('   ');
    fetchWorkspaceCapabilities.mockClear();
    const { refresh, setWanted, profile, loading } = useSpaceCapabilities({
      workspaceDataDir: blankDir,
    });
    await refresh();

    expect(fetchWorkspaceCapabilities).not.toHaveBeenCalled();
    expect(profile.value).toBeNull();
    expect(loading.value).toBe(false);

    const result = await setWanted('projects', true);
    expect(result.ok).toBe(false);
    expect(result.error).toBe('no_workspace');
    expect(updateWorkspaceCapabilitiesWanted).not.toHaveBeenCalled();
  });

  it('ignore setWanted result when active space changes during PUT', async () => {
    const staleProfile = {
      wanted: { regards: true },
      items: [
        {
          id: 'regards',
          status: 'active',
          wanted: true,
          entitled: true,
        },
      ],
      effectiveIds: ['regards'],
      cloudWanted: false,
      cloudEntitled: true,
    };
    const otherSpaceProfile = {
      wanted: { projects: true },
      items: [
        {
          id: 'projects',
          status: 'active',
          wanted: true,
          entitled: true,
        },
      ],
      effectiveIds: ['projects'],
      cloudWanted: true,
      cloudEntitled: true,
    };

    const { refresh, setWanted, profile } = useSpaceCapabilities();
    await refresh();
    profile.value = staleProfile as typeof profile.value;

    let resolvePut!: (value: unknown) => void;
    const putPromise = new Promise((resolve) => {
      resolvePut = resolve;
    });
    updateWorkspaceCapabilitiesWanted.mockReturnValue(putPromise);
    fetchWorkspaceCapabilities.mockReturnValue(new Promise(() => {}));

    const setPromise = setWanted('regards', false);
    activeDataDir.value = '/tmp/other-ws';
    resolvePut({
      ok: true,
      data: otherSpaceProfile,
    });

    const result = await setPromise;
    expect(result.ok).toBe(false);
    expect(result.autoWantedCloud).toBe(false);
    expect(profile.value).toEqual(staleProfile);
  });
});
