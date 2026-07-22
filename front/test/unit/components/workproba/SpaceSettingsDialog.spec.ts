import { nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SpaceSettingsDialog from '@components/workproba/SpaceSettingsDialog.vue';
import type { WorkspaceInfo } from '@composables/useDesktop.types';
import type { SpaceCapabilityItem } from '@services/aiSidecar';

const openCapabilities = vi.fn();
const setupItem: SpaceCapabilityItem = {
  id: 'projects',
  status: 'unavailable',
  wanted: false,
  entitled: true,
  unavailableReason: 'parent_cloud_off',
};

const workspace: WorkspaceInfo = {
  id: 'ws-1',
  title: 'Mon espace',
  folderPath: '/tmp/mon-espace',
  dataDir: '/tmp/mon-espace/.workproba',
};

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    renameSpace: vi.fn(),
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    openCapabilities,
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

describe('SpaceSettingsDialog', () => {
  beforeEach(() => {
    openCapabilities.mockClear();
  });

  it('ferme la modale puis ouvre le hub capacités sur open-setup', async () => {
    const wrapper = mount(SpaceSettingsDialog, {
      props: {
        modelValue: true,
        workspace,
      },
      global: {
        stubs: {
          Lucide: true,
          SpaceCapabilitiesPanel: {
            template: '<button data-testid="setup" @click="$emit(\'open-setup\', item)">setup</button>',
            props: ['workspaceDataDir', 'embedded'],
            data() {
              return { item: setupItem };
            },
          },
          'q-dialog': {
            template: '<div><slot /></div>',
            props: ['modelValue'],
          },
        },
      },
    });

    await wrapper.find('[data-testid="setup"]').trigger('click');
    await nextTick();

    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false]);
    expect(openCapabilities).toHaveBeenCalledWith('workproba_cloud');
  });
});
