import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import WorkprobaTitleBar from '@components/workproba/WorkprobaTitleBar.vue';
import { WORKPROBA_CLOUD_BUILTIN_SET } from '@utils/providerSets';

const push = vi.fn();

const mockUseAppSettings = vi.fn(() => ({
  activeSet: { value: null },
  effectiveActiveSet: { value: null },
  activeChatProvider: { value: null },
  activeEmbeddingProvider: { value: null },
  settingsLocked: { value: false },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => mockUseAppSettings(),
}));

const mountTitleBar = (props: Record<string, unknown> = {}) =>
  mount(WorkprobaTitleBar, {
    props: {
      workspaceTitle: null,
      activePath: null,
      rightPanelOpen: false,
      sidebarRail: false,
      ...props,
    },
    global: {
      stubs: {
        Lucide: true,
        CapabilitiesButton: true,
        ThemeToggler: true,
        WorkprobaBrand: true,
        'q-tooltip': true,
        'q-dialog': true,
        'q-menu': true,
        'q-list': true,
        'q-item': true,
        'q-item-section': true,
        'q-separator': true,
      },
    },
  });

describe('WorkprobaTitleBar', () => {
  it('affiche le chip en erreur sans effectiveActiveSet même si sidecar connecté', () => {
    mockUseAppSettings.mockReturnValue({
      activeSet: { value: null },
      effectiveActiveSet: { value: null },
      activeChatProvider: { value: null },
      activeEmbeddingProvider: { value: null },
      settingsLocked: { value: false },
    });

    const wrapper = mountTitleBar({ sidecarState: 'connected' });

    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--error');
  });

  it('affiche le label cloud et le chip en erreur quand activeSet est défini mais pas effectiveActiveSet', () => {
    mockUseAppSettings.mockReturnValue({
      activeSet: { value: WORKPROBA_CLOUD_BUILTIN_SET },
      effectiveActiveSet: { value: null },
      activeChatProvider: { value: null },
      activeEmbeddingProvider: { value: null },
      settingsLocked: { value: false },
    });

    const wrapper = mountTitleBar({ sidecarState: 'connected' });

    expect(wrapper.find('.wp-titlebar__chip-label').text()).toBe('Improba Cloud');
    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--error');
  });

  it('navigue vers l\'accueil au clic sur Workproba', async () => {
    mockUseAppSettings.mockReturnValue({
      activeSet: { value: null },
      effectiveActiveSet: { value: null },
      activeChatProvider: { value: null },
      activeEmbeddingProvider: { value: null },
      settingsLocked: { value: false },
    });

    push.mockClear();

    const wrapper = mountTitleBar({
      workspaceTitle: 'kaggle',
      activePath: '/tmp/kaggle',
    });

    await wrapper.find('.wp-titlebar__mark').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'home' });
  });
});
