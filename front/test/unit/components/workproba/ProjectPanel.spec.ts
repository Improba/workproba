import { computed, ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setLang } from '@boot/i18n';
import ProjectPanel from '@components/workproba/ProjectPanel.vue';
import { openPath } from '@composables/useDesktop';

const enrolled = ref(false);
const canSync = ref(false);
const mockRefreshStatus = vi.fn().mockResolvedValue(undefined);
const mockStatus = ref<{ enrolled?: boolean } | null>({ enrolled: false });

const { getPluginDataDir, listProjetProjects, listProjetPublishedDocuments, listProjetArtefactSyncStatus, listCloudArtefacts, openCloudArtefact } =
  vi.hoisted(() => ({
    getPluginDataDir: vi.fn(),
    listProjetProjects: vi.fn(),
    listProjetPublishedDocuments: vi.fn(),
    listProjetArtefactSyncStatus: vi.fn(),
    listCloudArtefacts: vi.fn(),
    openCloudArtefact: vi.fn(),
  }));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: mockStatus,
    isEnrolled: computed(() => enrolled.value),
    isActive: computed(() => enrolled.value),
    canSync: computed(() => canSync.value),
    init: vi.fn().mockResolvedValue(undefined),
    refreshStatus: mockRefreshStatus,
  }),
}));

vi.mock('@composables/usePlugins', () => ({
  CLOUD_PLUGIN_ID: 'workproba.cloud',
  PROJET_PLUGIN_ID: 'workproba.projet',
  usePlugins: () => ({
    getPluginDataDir,
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  openPath: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('@services/aiSidecar', () => ({
  listProjetProjects,
  listProjetPublishedDocuments,
  listProjetArtefactSyncStatus,
  listCloudArtefacts,
  openCloudArtefact,
  createProjetProject: vi.fn(),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

function mountPanel() {
  return mount(ProjectPanel, {
    global: {
      stubs: {
        Lucide: true,
      },
    },
  });
}

describe('ProjectPanel', () => {
  beforeEach(() => {
    enrolled.value = false;
    canSync.value = false;
    mockStatus.value = { enrolled: false };
    mockRefreshStatus.mockClear();
    listProjetPublishedDocuments.mockClear();
    listProjetArtefactSyncStatus.mockClear();
    listCloudArtefacts.mockClear();
    openCloudArtefact.mockClear();
    vi.mocked(openPath).mockClear();
    getPluginDataDir.mockImplementation(async (pluginId: string) =>
      pluginId === 'workproba.projet' ? '/data/projet' : '/data/cloud',
    );
    listProjetProjects.mockResolvedValue({
      ok: true,
      data: [{ id: 'p1', name: 'Docs locaux' }],
    });
    listProjetPublishedDocuments.mockResolvedValue({ ok: true, data: [] });
    listProjetArtefactSyncStatus.mockResolvedValue({ ok: true, data: [] });
    listCloudArtefacts.mockResolvedValue({ ok: true, data: [] });
  });

  it('affiche les libellés bibliothèque quand la synchronisation est inactive', async () => {
    setLang('fr');
    enrolled.value = false;
    canSync.value = false;

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('label[for="project-select"]').text()).toBe('Bibliothèque');
    expect(wrapper.find('.project-panel__scope-hint').text()).toContain('ce poste uniquement');
  });

  it('affiche les libellés bibliothèque en mount-only (configured, pas enrollé)', async () => {
    setLang('fr');
    enrolled.value = false;
    canSync.value = true;

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('label[for="project-select"]').text()).toBe('Bibliothèque');
    expect(wrapper.find('.project-panel__scope-hint').text()).toContain('ce poste uniquement');
  });

  it('affiche les libellés projet quand cloud enrollé', async () => {
    setLang('fr');
    enrolled.value = true;
    canSync.value = true;
    mockStatus.value = { enrolled: true };

    const wrapper = mountPanel();
    await flushPromises();

    expect(mockRefreshStatus).toHaveBeenCalled();
    expect(wrapper.find('label[for="project-select"]').text()).toBe('Projet');
    expect(wrapper.find('.project-panel__scope-hint').text()).toContain('Projet partagé cloud');
    expect(wrapper.find('.project-panel__docs-title').text()).toBe('Documents de l\'organisation');
    expect(listCloudArtefacts).toHaveBeenCalledWith('/data/cloud', 'p1');
    expect(listProjetPublishedDocuments).not.toHaveBeenCalled();
    expect(listProjetArtefactSyncStatus).not.toHaveBeenCalled();
  });

  it('charge les documents locaux quand non enrollé', async () => {
    setLang('fr');
    enrolled.value = false;

    mountPanel();
    await flushPromises();

    expect(listProjetPublishedDocuments).toHaveBeenCalledWith('/data/projet', 'p1');
    expect(listCloudArtefacts).not.toHaveBeenCalled();
  });

  it('ouvre un document cloud au clic quand enrollé', async () => {
    enrolled.value = true;
    mockStatus.value = { enrolled: true };
    listCloudArtefacts.mockResolvedValue({
      ok: true,
      data: [
        {
          id: 'note.md',
          name: 'note.md',
          project_id: 'p1',
          created_at: '2026-07-16T12:00:00.000Z',
          cloud_confirmed: true,
        },
      ],
    });
    openCloudArtefact.mockResolvedValue({
      ok: true,
      data: {
        local_path: '/data/cloud/cache/p1/note.md/v1.0.0/note.md',
        artefact_id: 'note.md',
        version: '1.0.0',
        filename: 'note.md',
      },
    });

    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.project-panel__doc').trigger('click');
    await flushPromises();

    expect(openCloudArtefact).toHaveBeenCalledWith({
      pluginDataDir: '/data/cloud',
      projectId: 'p1',
      artefactId: 'note.md',
    });
    expect(openPath).toHaveBeenCalledWith('/data/cloud/cache/p1/note.md/v1.0.0/note.md');
  });

  it('n’affiche le badge cloud que si cloud_confirmed est true', async () => {
    enrolled.value = true;
    mockStatus.value = { enrolled: true };
    listCloudArtefacts.mockResolvedValue({
      ok: true,
      data: [
        {
          id: 'confirmed.md',
          name: 'confirmed.md',
          project_id: 'p1',
          created_at: '2026-07-16T12:00:00.000Z',
          cloud_confirmed: true,
        },
        {
          id: 'pending.md',
          name: 'pending.md',
          project_id: 'p1',
          created_at: '2026-07-16T12:00:00.000Z',
          cloud_confirmed: false,
          cloud_pending: true,
        },
      ],
    });

    const wrapper = mountPanel();
    await flushPromises();

    const badges = wrapper.findAll('.project-panel__badge--cloud');
    expect(badges).toHaveLength(1);
    expect(wrapper.text()).toContain('pending.md');
    expect(wrapper.findAll('.project-panel__badge--pending')).toHaveLength(1);
  });
});
