import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import WorkprobaTitleBar from '@components/workproba/WorkprobaTitleBar.vue';

const push = vi.fn();

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    activeSet: { value: null },
    effectiveActiveSet: { value: null },
    activeChatProvider: { value: null },
    activeEmbeddingProvider: { value: null },
    settingsMode: { value: 'guided' },
    settingsLocked: { value: false },
  }),
}));

describe('WorkprobaTitleBar', () => {
  it('affiche le chip en erreur sans effectiveActiveSet même si sidecar connecté', () => {
    const wrapper = mount(WorkprobaTitleBar, {
      props: {
        workspaceTitle: null,
        activePath: null,
        rightPanelOpen: false,
        sidebarRail: false,
        sidecarState: 'connected',
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

    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--error');
  });

  it('navigue vers l\'accueil au clic sur Workproba', async () => {
    push.mockClear();

    const wrapper = mount(WorkprobaTitleBar, {
      props: {
        workspaceTitle: 'kaggle',
        activePath: '/tmp/kaggle',
        rightPanelOpen: false,
        sidebarRail: false,
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

    await wrapper.find('.wp-titlebar__mark').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'home' });
  });
});
