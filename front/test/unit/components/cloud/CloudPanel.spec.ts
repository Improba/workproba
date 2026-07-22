import { computed, ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CloudPanel from '@components/cloud/CloudPanel.vue';
import ManagedConnectorsSection from '@components/cloud/ManagedConnectorsSection.vue';
import { PROJET_PLUGIN_ID } from '@composables/usePlugins';

const mockEnroll = vi.fn();
const mockDisconnect = vi.fn();
const mockSync = vi.fn();
const mockPull = vi.fn();
const mockSyncRegards = vi.fn();
const mockRefreshConnectors = vi.fn().mockResolvedValue(undefined);
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
const mockLoading = ref(false);

const settingsLocked = ref(false);
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
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: mockStatus,
    loading: mockLoading,
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
    connectors: ref([]),
    connectorsLoading: ref(false),
    connectorsError: ref(null),
    quota: ref(null),
    quotaLoading: ref(false),
    quotaError: ref(null),
    providerReadiness: ref(null),
    isEnrolled: computed(() => Boolean(mockStatus.value?.enrolled)),
    isActive: computed(() => Boolean(mockStatus.value?.enrolled)),
    canSync: computed(() => Boolean(mockStatus.value?.configured || mockStatus.value?.enrolled)),
    refreshConnectors: mockRefreshConnectors,
    refreshQuota: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('@composables/usePersonas', () => ({
  usePersonas: () => ({
    refresh: mockRefreshPersonas,
  }),
}));

vi.mock('@services/aiSidecar', () => ({
  listProjetProjects,
  resolveUiMode: (locked: boolean) => (locked ? 'locked' : 'agent'),
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
      if (params?.count !== undefined && params?.lastSync !== undefined) {
        return `${key}:${params.count}:${params.lastSync}`;
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
    global: {
      stubs: {
        Lucide: true,
        EnrollCloudJoinForm: false,
        CloudLoginModal: true,
        EnrollCloudModal: true,
      },
    },
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
    mockLoading.value = false;
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

  it('affiche la section projets en mode agent même non enrollé', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.projectsTitle');
  });

  it('n’affiche pas la section projets en mode verrouillé non enrollé', async () => {
    settingsLocked.value = true;
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).not.toContain('cloud.projectsTitle');
    expect(wrapper.find('.cloud-panel__projects').exists()).toBe(false);
  });

  it('affiche la connexion principale en mode verrouillé non enrollé', async () => {
    settingsLocked.value = true;
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.loginTitle');
    expect(wrapper.text()).toContain('cloud.loginSubmit');
    expect(wrapper.text()).toContain('cloud.haveInvitationCode');
    expect(wrapper.find('#cloud-join-token').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('cloud.bearerToken');
    expect(wrapper.text()).not.toContain('cloud.advancedOptions');
    expect(wrapper.text()).not.toContain('cloud.connectedBadge');
    expect(wrapper.text()).not.toContain('cloud.experimental');
  });

  it('affiche le formulaire join après clic invitation', async () => {
    settingsLocked.value = true;
    const wrapper = mountPanel();
    await flushPromises();

    const invitationBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('cloud.haveInvitationCode'));
    await invitationBtn!.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.joinTitle');
    expect(wrapper.text()).toContain('cloud.joinSubmit');
    expect(wrapper.find('#cloud-join-token').exists()).toBe(true);
  });

  it('affiche connecté à org quand enrollé en mode verrouillé', async () => {
    settingsLocked.value = true;
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
      synced_count: 3,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.connectedTo:Acme RH');
    expect(wrapper.text()).toContain('cloud.syncMeta:3:cloud.neverSynced');
    expect(wrapper.text()).toContain('cloud.disconnect');
    expect(wrapper.text()).not.toContain('cloud.bearerToken');
    expect(wrapper.find('.cloud-panel__sync-btn').exists()).toBe(false);
    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(false);
    expect(wrapper.text()).toContain('cloud.localOptions');
    expect(wrapper.text()).not.toContain('cloud.connectedBadge');
  });

  it('affiche le pull après ouverture des options locales en mode verrouillé enrollé', async () => {
    settingsLocked.value = true;
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(false);

    const localOptionsBtn = wrapper
      .findAll('.cloud-panel__link-btn')
      .find((btn) => btn.text().includes('cloud.localOptions'));
    expect(localOptionsBtn).toBeDefined();
    await localOptionsBtn!.trigger('click');
    await flushPromises();

    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(true);
    expect(wrapper.text()).toContain('cloud.hideLocalOptions');
  });

  it('affiche le pull et masque le sync quand enrollé en mode avancé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: true,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).not.toContain('cloud.pushLocalCache');
    expect(wrapper.text()).toContain('cloud.reloadCache');
    expect(wrapper.find('.cloud-panel__sync-btn').exists()).toBe(false);
    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(true);
  });

  it('affiche les opérations de cache en mode avancé non enrollé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.pushLocalCache');
    expect(wrapper.find('.cloud-panel__sync-btn').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('cloud.reloadCache');
    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(false);
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

    await wrapper.find('.cloud-panel__link-btn--danger').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'cloud.disconnectConfirmTitle',
        message: 'cloud.disconnectConfirmMessage:Acme RH',
      }),
    );
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('réinitialise le dossier local après déconnexion réussie', async () => {
    settingsLocked.value = true;
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };
    mockDisconnect.mockImplementation(async () => {
      mockStatus.value = { ...mockStatus.value, enrolled: false, org_label: null };
      return true;
    });

    const wrapper = mountPanel();
    await flushPromises();

    const localOptionsBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('cloud.localOptions'));
    await localOptionsBtn!.trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('cloud.hideLocalOptions');

    await wrapper.find('.cloud-panel__link-btn--danger').trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.loginTitle');
    expect(wrapper.text()).not.toContain('cloud.hideLocalOptions');
    expect(wrapper.text()).not.toContain('cloud.localOptions');
  });

  it('rafraîchit les projets après un join réussi', async () => {
    settingsLocked.value = true;
    mockEnroll.mockImplementation(async () => {
      mockStatus.value = {
        ...mockStatus.value,
        enrolled: true,
        org_label: 'Acme RH',
        base_url: 'https://cloud.preset.test',
      };
      return true;
    });

    const wrapper = mountPanel();
    await flushPromises();
    listProjetProjects.mockClear();

    const invitationBtn = wrapper
      .findAll('button')
      .find((btn) => btn.text().includes('cloud.haveInvitationCode'));
    await invitationBtn!.trigger('click');
    await flushPromises();

    await wrapper.find('#cloud-join-token').setValue('invite-1');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(mockEnroll).toHaveBeenCalled();
    expect(listProjetProjects).toHaveBeenCalled();
    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'cloud.joinSuccess' }),
    );
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

    await wrapper.find('.cloud-panel__link-btn--danger').trigger('click');
    await flushPromises();

    expect(mockDialogCreate).toHaveBeenCalled();
    expect(mockDisconnect).not.toHaveBeenCalled();
  });

  it('demande confirmation avant synchronisation', async () => {
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

  it('n’affiche pas le pull hors enrollment en mode avancé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      configured: true,
      enrolled: false,
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('.cloud-panel__pull-btn').exists()).toBe(false);
    expect(mockPull).not.toHaveBeenCalled();
  });

  it('demande confirmation avant pull quand enrollé en mode avancé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
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

  it('affiche la section connecteurs quand enrollé en mode verrouillé', async () => {
    settingsLocked.value = true;
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.findComponent(ManagedConnectorsSection).exists()).toBe(true);
  });

  it('affiche la section connecteurs quand enrollé en mode agent', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.findComponent(ManagedConnectorsSection).exists()).toBe(true);
  });

  it('affiche le bouton de mise à jour des regards quand enrollé en mode verrouillé', async () => {
    settingsLocked.value = true;
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.syncRegards');
    const regardsBtn = wrapper
      .findAll('.cloud-panel__save-btn')
      .find((btn) => btn.text().includes('cloud.syncRegards'));
    expect(regardsBtn).toBeDefined();
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

    const regardsBtn = wrapper
      .findAll('.cloud-panel__save-btn')
      .find((btn) => btn.text().includes('cloud.syncRegards'));
    await regardsBtn!.trigger('click');
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

    const regardsBtn = wrapper
      .findAll('.cloud-panel__save-btn')
      .find((btn) => btn.text().includes('cloud.syncRegards'));
    await regardsBtn!.trigger('click');
    await flushPromises();

    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'cloud.syncRegardsFailed',
        color: 'negative',
      }),
    );
  });

  it('affiche le panneau technique en mode avancé', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.technicalSettings');
    expect(wrapper.text()).toContain('cloud.bearerToken');
    expect(wrapper.text()).toContain('cloud.mountPathTitle');
  });

  it('affiche sync regards et déconnexion quand enrollé en mode avancé', async () => {
    mockStatus.value = {
      ...mockStatus.value,
      enrolled: true,
      org_label: 'Acme RH',
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('cloud.connectedTo:Acme RH');
    expect(wrapper.text()).toContain('cloud.syncRegards');
    expect(wrapper.text()).toContain('cloud.disconnect');
    expect(wrapper.text()).not.toContain('cloud.localOptions');
  });

  it('n’appelle pas listProjetProjects si le plugin projet est inactif', async () => {
    isProjetPluginActive.value = false;

    mountPanel();
    await flushPromises();

    expect(listProjetProjects).not.toHaveBeenCalled();
  });

  it('affiche uniquement le chargement initial sans formulaire join', async () => {
    mockLoading.value = true;
    mockStatus.value = null as unknown as typeof mockStatus.value;

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain('common.loading');
    expect(wrapper.text()).not.toContain('cloud.joinTitle');
    expect(wrapper.find('#cloud-join-token').exists()).toBe(false);
  });
});
