import { ref } from 'vue';
import { shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SpaceCapabilitiesPanel from '@components/capabilities/SpaceCapabilitiesPanel.vue';
import type { SpaceCapabilityItem } from '@services/aiSidecar';

const openCapabilities = vi.fn();
const unavailableItem: SpaceCapabilityItem = {
  id: 'projects',
  status: 'unavailable',
  wanted: false,
  entitled: true,
  unavailableReason: 'parent_cloud_off',
};

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    activeDataDir: ref('/tmp/ws'),
  }),
}));

vi.mock('@composables/useSpaceCapabilities', () => ({
  useSpaceCapabilities: () => ({
    loading: ref(false),
    error: ref(null),
    profile: ref({ wanted: {}, items: [unavailableItem], effectiveIds: [] }),
    activeItems: ref([]),
    availableItems: ref([]),
    unavailableItems: ref([unavailableItem]),
    setWanted: vi.fn(),
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

describe('SpaceCapabilitiesPanel', () => {
  beforeEach(() => {
    openCapabilities.mockClear();
  });

  function mountPanel(embedded = false) {
    return shallowMount(SpaceCapabilitiesPanel, {
      props: {
        workspaceDataDir: '/tmp/ws',
        embedded,
      },
      global: {
        stubs: {
          Lucide: true,
          SpaceCapabilityRow: {
            template: '<button data-testid="setup" @click="$emit(\'open-setup\', item)">setup</button>',
            props: ['item'],
          },
        },
      },
    });
  }

  it('émet open-setup en mode embedded', async () => {
    const wrapper = mountPanel(true);
    await wrapper.find('[data-testid="setup"]').trigger('click');

    expect(wrapper.emitted('open-setup')?.[0]).toEqual([unavailableItem]);
    expect(openCapabilities).not.toHaveBeenCalled();
  });

  it('ouvre les capacités directement hors mode embedded', async () => {
    const wrapper = mountPanel(false);
    await wrapper.find('[data-testid="setup"]').trigger('click');

    expect(wrapper.emitted('open-setup')).toBeUndefined();
    expect(openCapabilities).toHaveBeenCalledWith('workproba_cloud');
  });
});
