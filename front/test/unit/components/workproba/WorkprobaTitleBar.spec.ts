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
    activeChatProvider: { value: null },
    activeEmbeddingProvider: { value: null },
    settingsMode: { value: 'guided' },
    settingsLocked: { value: false },
  }),
}));

describe('WorkprobaTitleBar', () => {
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
