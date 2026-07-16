import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setLang } from '@boot/i18n';
import VersionsPanel from '@components/workproba/VersionsPanel.vue';

const versions = ref([
  {
    version_id: 'v1',
    created_at: '2026-01-01T00:00:00Z',
    size: 120,
    label: 'Avant modification IA',
  },
]);
const loading = ref(false);
const restoring = ref(false);
const purging = ref(false);
const lastRestore = ref(null);
const pendingRestore = ref<{
  filePath: string;
  versionId: string;
  entry: (typeof versions.value)[number];
} | null>(null);

const {
  openRestoreConfirm,
  closeRestoreConfirm,
  restoreVersion,
  listVersions,
  purgeVersions,
  undoRestore,
  clearRestoreBanner,
} = vi.hoisted(() => ({
  openRestoreConfirm: vi.fn(),
  closeRestoreConfirm: vi.fn(),
  restoreVersion: vi.fn(),
  listVersions: vi.fn(),
  purgeVersions: vi.fn(),
  undoRestore: vi.fn(),
  clearRestoreBanner: vi.fn(),
}));

vi.mock('@composables/useVersions', () => ({
  useVersions: () => ({
    versions,
    loading,
    restoring,
    purging,
    lastRestore,
    pendingRestore,
    listVersions,
    openRestoreConfirm,
    closeRestoreConfirm,
    restoreVersion,
    purgeVersions,
    undoRestore,
    clearRestoreBanner,
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

function mountPanel() {
  return shallowMount(VersionsPanel, {
    props: {
      relativePath: 'docs/note.txt',
      projectPath: '/data/project',
      workspaceDataDir: '/data/ws',
    },
    global: {
      stubs: {
        'q-dialog': { template: '<div class="q-dialog-stub"><slot /></div>' },
        RestoreBanner: true,
      },
    },
  });
}

describe('VersionsPanel restore confirm', () => {
  beforeEach(() => {
    setLang('fr');
    loading.value = false;
    restoring.value = false;
    pendingRestore.value = null;
    openRestoreConfirm.mockClear();
    closeRestoreConfirm.mockClear();
  });

  it('ouvre la confirmation au clic restaurer', async () => {
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.find('.versions-panel__restore').trigger('click');

    expect(openRestoreConfirm).toHaveBeenCalledWith('docs/note.txt', 'v1');
    wrapper.unmount();
  });

  it('affiche le dialog quand pendingRestore est défini et annule via closeRestoreConfirm', async () => {
    pendingRestore.value = {
      filePath: 'docs/note.txt',
      versionId: 'v1',
      entry: versions.value[0],
    };

    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.find('.versions-restore-dialog').exists()).toBe(true);

    await wrapper.find('.versions-restore-dialog__btn--ghost').trigger('click');

    expect(closeRestoreConfirm).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
