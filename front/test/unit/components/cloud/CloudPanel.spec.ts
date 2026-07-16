import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CloudPanel from '@components/cloud/CloudPanel.vue';
import { PROJET_PLUGIN_ID } from '@composables/usePlugins';

const mockEnroll = vi.fn();
const mockDisconnect = vi.fn();
const mockSync = vi.fn();
const mockPull = vi.fn();
const mockSyncRegards = vi.fn();
const mockRefreshPersonas = vi.fn().mockResolvedValue(undefined);
const mockStatus = ref({
  configured: false,
  mount_path: null,
  synced_count: 0,
  last_sync: null,
  enrolled: false,
  has_token: false,
  base_url: null,
  org_id: null,
  org_label: null,
});

const settingsLocked = ref(false);
const settingsMode = ref<'guided' | 'advanced'>('guided');
const mockLoadError = ref<string | null>(null);

const { getPluginDataDir, listProjetProjects, isProjetPluginActive } = vi.hoisted(() => ({
  getPluginDataDir: vi.fn(),
  listProjetProjects: vi.fn(),
  isProjetPluginActive: { value: true },
}));

const mockDialogCreate = vi.hoisted(() => vi.fn());
const mockNotifyCreate = vi.hoisted(() => vi.fn());

vi.mock('@composables/usePlugins', () => ({
  CLOUD_PLUGIN_ID: 'workproba.cloud',
  PROJET_PLUGIN_ID: 'workproba.projet',
  PERSONAS_PLUGIN_ID: 'workproba.personas',
  usePlugins: () => ({
    isCloudPluginActive: { value: true },
    isProjetPluginActive,
    getPluginDataDir,
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settings: ref({ cloudEndpoint: 'https://cloud.preset.test' }),
    settingsLocked,
    settingsMode,
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: mockStatus,
    loading: ref(false),
    syncing: ref(false),
    pulling: ref(false),
    loadError: mockLoadError,
    init: vi.fn().mockResolvedValue(undefined),
    refreshStatus: vi.fn().mockResolvedValue(undefined),
    configure: vi.fn(),
    enroll: mockEnroll,
    disconnect: mockDisconnect,
    sync: mockSync,
    pull: mockPull,
    syncRegards: mockSyncRegards,
    syncingRegards: ref(false),
  }),
}));

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    refresh: mockRefreshPersonas,
  }),
}));

vi.mock('@services/aiSidecar', () => ({
  listProjetProjects,
  resolveUiMode: (locked: boolean, mode: string) => (locked ? 'locked' : mode),
}));

vi.mock('@composables/useDesktop', () => ({
  pickProjectFolder: vi.fn(),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      if (params?.org) return `${key}:${params.org}`;
      if (params?.error) return `${key}:${params.error}`;
      if (params?.count !== undefined && params?.detail !== undefined) {
        return `${key}:${params.count}:${params.detail}`;
      }
      if (params?.count !== undefined) return `${key}:${params.count}`;
      return key;
    },
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: mockNotifyCreate },
  Dialog: { create: mockDialogCreate },
}));

function mountPanel() {
  return shallowMount(CloudPanel, {
    global: { stubs: { Lucide: true } },
  });
}

function mockDialogConfirm(confirmed: boolean): void {
  mockDialogCreate.mockImplementation(() => {
    const chain = {
      onOk: vi.fn((cb: () => void) => {
        if (confirmed) cb();
        return chain;
      }),
      onCancel: vi.fn((cb: () => void) => {
        if (!confirmed) cb();
        return chain;
      }),
      onDismiss: vi.fn(() => chain),
    };
    return chain;
  });
}

describe('CloudPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    settingsLocked.value = false;
    settingsMode.value = 'guided';
    mockLoadError.value = null;
    mockStatus.value = {
      configured: false,
      mount_path: null,
      synced_count: 0,
      last_sync: null,
      enrolled: false,
      has_token: false,
      base_url: null,
      org_id: null,
      org_label: null,
    };
    isProjetPluginActive.value = true;
    getPluginDataDir.mockImplementation(async (pluginId: string) => {
      if (pluginId === 'workproba.personas') return '/data/workproba.personas';
      return '/data/workproba.projet';
    });
    listProjetProjects.mockResolvedValue({
      ok: true,
      data: [{ id: 'p1', name: 'Alpha' }],
    });
    mockEnroll.mockResolvedValue(true);
    mockDisconnect.mockResolvedValue(true);
    mockSync.mockResolvedValue({ ok: true, data: { synced: [] } });
    mockPull.mockResolvedValue({ ok: true, data: { pulled: [] } });
    mockSyncRegards.mockResolvedValue({ ok: true, data: { count: 1, installed: [] } });
    mockDialogConfirm(true);
  });

  it('uses projet plugin data dir to list projects', async () => {
    mountPanel();
    await flushPromises();

    expect(getPluginDataDir).toHaveBeenCalledWith(PROJET_PLUGIN_ID);
    expect(listProjetProjects).toHaveBeenCalledWith('/data/workproba.projet');
  });

  it('affiche le formulaire join en mode guidé non enrollé', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.joinTitle');
    expect(wrapper.text()).toContain('cloud.join');
    expect(wrapper.find('input[type="text"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('cloud.bearerToken');
  });

  it('affiche connecté à org quand enrollé en mode guidé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
      synced_count: 3,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.connectedTo:Acme RH');
    expect(wrapper.text()).toContain('cloud.statusSyncedCount');
    expect(wrapper.text()).toContain('cloud.disconnect');
    expect(wrapper.text()).not.toContain('cloud.bearerToken');
    expect(wrapper.find('.cloud-panel__sync-btn').exists()).toBe(false);
    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(false);
    expect(wrapper.text()).toContain('cloud.cacheOptions');
  });

  it('masque les opérations de cache quand enrollé en mode avancé', async () => {
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: true,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).not.toContain('cloud.pushLocalCache');
    expect(wrapper.text()).not.toContain('cloud.reloadCache');
    expect(wrapper.find('.cloud-panel__sync-btn').exists()).toBe(false);
    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(false);
  });

  it('affiche les opérations de cache en mode avancé non enrollé', async () => {
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.pushLocalCache');
    expect(wrapper.text()).toContain('cloud.reloadCache');
    expect(wrapper.find('.cloud-panel__sync-btn').exists()).toBe(true);
    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(true);
  });

  it('humanise les erreurs techniques en mode guidé', async () => {
    mockLoadError.value = 'cloud_status_failed';

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.loadFailed');
    expect(wrapper.text()).not.toContain('cloud_status_failed');
  });

  it('demande confirmation avant déconnexion', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__disconnect-btn').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'cloud.disconnectConfirmTitle',
        message: 'cloud.disconnectConfirmMessage:Acme RH',
      }),
    );
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('n’appelle pas disconnect si la confirmation est annulée', async () => {
    mockDialogConfirm(false);
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__disconnect-btn').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalled();
    expect(mockDisconnect).not.toHaveBeenCalled();
  });

  it('demande confirmation avant synchronisation', async () => {
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__sync-btn').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'cloud.syncConfirmTitle',
        message: 'cloud.syncConfirmMessage',
      }),
    );
    expect(mockSync).toHaveBeenCalledWith('p1');
  });

  it('n’appelle pas sync si la confirmation est annulée', async () => {
    mockDialogConfirm(false);
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__sync-btn').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalled();
    expect(mockSync).not.toHaveBeenCalled();
  });

  it('demande confirmation avant pull', async () => {
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__pull-btn').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'cloud.pullConfirmTitle',
        message: 'cloud.pullConfirmMessage',
      }),
    );
    expect(mockPull).toHaveBeenCalledWith('p1');
  });

  it('n’appelle pas pull si la confirmation est annulée', async () => {
    mockDialogConfirm(false);
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__pull-btn').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalled();
    expect(mockPull).not.toHaveBeenCalled();
  });

  it('affiche une notification négative si le pull retourne des erreurs', async () => {
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };
    mockPull.mockResolvedValue({
      ok: true,
      data: { pulled: ['doc.pdf'], errors: ['doc2.pdf: timeout', 'doc3.pdf: checksum'] },
    });

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__pull-btn').trigger('click');
    await flushPromises();

    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'cloud.pullErrorsNotify:2:doc2.pdf: timeout; doc3.pdf: checksum',
        color: 'negative',
      }),
    );
  });

  it('affiche une notification info si le pull retourne des skipped', async () => {
    settingsMode.value = 'advanced';
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };
    mockPull.mockResolvedValue({
      ok: true,
      data: {
        pulled: [],
        skipped: ['contrat.docx:local_up_to_date', 'note.md:not_confirmed'],
      },
    });

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__pull-btn').trigger('click');
    await flushPromises();

    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        message:
          'cloud.pullSkippedNotify:2:contrat.docx:local_up_to_date; note.md:not_confirmed',
        color: 'info',
      }),
    );
  });

  it('affiche le bouton de mise à jour des regards quand enrollé en mode guidé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.syncRegards');
    expect(wrapper.find('.cloud-panel__regards-btn').exists()).toBe(true);
  });

  it('notifie le succès après mise à jour des regards', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };
    mockSyncRegards.mockResolvedValue({ ok: true, data: { count: 2, installed: [] } });

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__regards-btn').trigger('click');
    await flushPromises();

    expect(mockSyncRegards).toHaveBeenCalled();
    expect(mockRefreshPersonas).toHaveBeenCalledWith('/data/workproba.personas');
    expect(wrapper.emitted('regardsChanged')).toHaveLength(1);
    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'cloud.syncRegardsSuccess:2',
        color: 'positive',
      }),
    );
  });

  it('notifie l\'échec si la mise à jour des regards échoue', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };
    mockSyncRegards.mockResolvedValue({ ok: false, error: 'cloud_sync_regards_failed' });

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.cloud-panel__regards-btn').trigger('click');
    await flushPromises();

    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'cloud.syncRegardsFailed',
        color: 'negative',
      }),
    );
  });

  it('affiche le panneau technique en mode avancé', async () => {
    settingsMode.value = 'advanced';

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.advancedOptions');
    expect(wrapper.text()).toContain('cloud.bearerToken');
    expect(wrapper.text()).toContain('cloud.mountPathTitle');
  });

  it('n’appelle pas listProjetProjects si le plugin projet est inactif', async () => {
    isProjetPluginActive.value = false;

    mountPanel();
    await flushPromises();

    expect(listProjetProjects).not.toHaveBeenCalled();
  });
});
