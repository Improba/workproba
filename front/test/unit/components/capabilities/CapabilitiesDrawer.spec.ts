import { ref } from 'vue';
import { flushPromises, shallowMount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CapabilitiesDrawer from '@components/capabilities/CapabilitiesDrawer.vue';

const capabilitiesOpen = ref(true);
const focusCapabilityId = ref<string | null>(null);
const closeCapabilities = vi.fn();
const activateAndOpen = vi.fn().mockResolvedValue(undefined);
const open = vi.fn();
const deactivate = vi.fn().mockResolvedValue(undefined);

const capabilities = ref([
  {
    definition: {
      id: 'projects',
      titleKey: 'capabilities.projects.title',
      descriptionKey: 'capabilities.projects.description',
      homeKey: 'capabilities.projects.home',
      icon: 'folder-kanban',
      pluginIds: ['workproba.projet'],
      primarySurface: { type: 'right_panel', tabKey: 'workproba.projet:right_panel' },
    },
    state: { kind: 'available' },
  },
]);

vi.mock('@composables/useCapabilities', () => ({
  useCapabilities: () => ({
    capabilities,
    activateAndOpen,
    open,
    deactivate,
    refreshManaged: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('@composables/useShellSurfaces', () => ({
  useShellSurfaces: () => ({
    capabilitiesOpen,
    focusCapabilityId,
    closeCapabilities,
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
  Dialog: {
    create: vi.fn(() => ({
      onOk: vi.fn().mockReturnThis(),
      onCancel: vi.fn().mockReturnThis(),
      onDismiss: vi.fn().mockReturnThis(),
    })),
  },
}));

describe('CapabilitiesDrawer', () => {
  beforeEach(() => {
    capabilitiesOpen.value = true;
    focusCapabilityId.value = null;
    activateAndOpen.mockClear();
    closeCapabilities.mockClear();
  });

  it('scroll vers la capacité focalisée', async () => {
    const scrollIntoView = vi.fn();
    vi.spyOn(document, 'querySelector').mockReturnValue({ scrollIntoView } as unknown as Element);

    shallowMount(CapabilitiesDrawer, {
      global: {
        stubs: {
          Lucide: true,
          CapabilityCard: true,
        },
      },
    });

    focusCapabilityId.value = 'projects';
    await flushPromises();

    expect(document.querySelector).toHaveBeenCalledWith('[data-capability-id="projects"]');
    expect(scrollIntoView).toHaveBeenCalled();
  });
});
