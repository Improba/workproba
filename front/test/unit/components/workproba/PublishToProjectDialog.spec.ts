import { computed, ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PublishToProjectDialog from '@components/workproba/PublishToProjectDialog.vue';

const enrolled = ref(false);
const canSync = ref(false);

const {
  getPluginDataDir,
  listProjetProjects,
  publishToProjet,
  publishToCloud,
} = vi.hoisted(() => ({
  getPluginDataDir: vi.fn(),
  listProjetProjects: vi.fn(),
  publishToProjet: vi.fn(),
  publishToCloud: vi.fn(),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    isEnrolled: computed(() => enrolled.value),
    canSync: computed(() => canSync.value),
    init: vi.fn().mockResolvedValue(undefined),
    sync: vi.fn(),
  }),
}));

vi.mock('@composables/usePlugins', () => ({
  CLOUD_PLUGIN_ID: 'workproba.cloud',
  PROJET_PLUGIN_ID: 'workproba.projet',
  usePlugins: () => ({
    getPluginDataDir,
  }),
}));

vi.mock('@services/aiSidecar', () => ({
  listProjetProjects,
  publishToProjet,
  publishToCloud,
  createProjetProject: vi.fn(),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

function mountDialog(overrides: Record<string, unknown> = {}) {
  return mount(PublishToProjectDialog, {
    props: {
      open: true,
      sourcePath: 'notes/doc.md',
      workspaceDataDir: '/workspace',
      ...overrides,
    },
    global: {
      stubs: { Lucide: true },
    },
  });
}

describe('PublishToProjectDialog', () => {
  beforeEach(() => {
    enrolled.value = false;
    canSync.value = false;
    publishToProjet.mockClear();
    publishToCloud.mockClear();
    getPluginDataDir.mockImplementation(async (pluginId: string) =>
      pluginId === 'workproba.projet' ? '/data/projet' : '/data/cloud',
    );
    listProjetProjects.mockResolvedValue({
      ok: true,
      data: [{ id: 'p1', name: 'Alpha' }],
    });
    publishToProjet.mockResolvedValue({
      ok: true,
      data: { name: 'doc.md' },
    });
  });

  it('publie toujours via publishToProjet même si enrollé', async () => {
    enrolled.value = true;
    canSync.value = true;

    const wrapper = mountDialog({ open: false });
    await wrapper.setProps({ open: true });
    await flushPromises();

    const publishBtn = wrapper
      .findAll('.publish-dialog__btn')
      .find((btn) => !btn.classes().includes('publish-dialog__btn--ghost'));
    expect(publishBtn).toBeDefined();
    await publishBtn!.trigger('click');
    await flushPromises();

    expect(publishToProjet).toHaveBeenCalledWith(
      expect.objectContaining({
        pluginDataDir: '/data/projet',
        projectId: 'p1',
        name: 'doc.md',
      }),
    );
    expect(publishToCloud).not.toHaveBeenCalled();
  });
});
