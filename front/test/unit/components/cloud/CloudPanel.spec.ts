import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CloudPanel from '@components/cloud/CloudPanel.vue';
import { PROJET_PLUGIN_ID } from '@composables/usePlugins';

const { getPluginDataDir, listProjetProjects, isProjetPluginActive } = vi.hoisted(() => ({
  getPluginDataDir: vi.fn(),
  listProjetProjects: vi.fn(),
  isProjetPluginActive: { value: true },
}));

vi.mock('@composables/usePlugins', () => ({
  CLOUD_PLUGIN_ID: 'workproba.cloud',
  PROJET_PLUGIN_ID: 'workproba.projet',
  usePlugins: () => ({
    isCloudPluginActive: { value: true },
    isProjetPluginActive,
    getPluginDataDir,
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: ref({
      configured: true,
      mount_path: '/mnt/cloud',
      synced_count: 0,
      last_sync: null,
    }),
    loading: ref(false),
    syncing: ref(false),
    loadError: ref(null),
    init: vi.fn().mockResolvedValue(undefined),
    refreshStatus: vi.fn().mockResolvedValue(undefined),
    configure: vi.fn(),
    sync: vi.fn().mockResolvedValue([]),
  }),
}));

vi.mock('@services/aiSidecar', () => ({
  listProjetProjects,
}));

vi.mock('@composables/useDesktop', () => ({
  pickProjectFolder: vi.fn(),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

describe('CloudPanel refreshProjects', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isProjetPluginActive.value = true;
    getPluginDataDir.mockResolvedValue('/data/workproba.projet');
    listProjetProjects.mockResolvedValue([{ id: 'p1', name: 'Alpha' }]);
  });

  it('uses projet plugin data dir to list projects', async () => {
    shallowMount(CloudPanel, {
      global: {
        stubs: { Lucide: true },
      },
    });
    await flushPromises();

    expect(getPluginDataDir).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(getPluginDataDir).not.toHaveBeenCalledWith('workproba.cloud');
    expect(listProjetProjects).toHaveBeenCalledWith('/data/workproba.projet');
  });

  it('n’appelle pas listProjetProjects si le plugin projet est inactif', async () => {
    isProjetPluginActive.value = false;

    shallowMount(CloudPanel, {
      global: {
        stubs: { Lucide: true },
      },
    });
    await flushPromises();

    expect(listProjetProjects).not.toHaveBeenCalled();
  });
});
