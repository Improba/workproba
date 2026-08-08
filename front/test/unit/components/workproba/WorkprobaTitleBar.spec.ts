import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import WorkprobaTitleBar from '@components/workproba/WorkprobaTitleBar.vue';

const push = vi.fn();
const organizationName = ref<string | null>(null);
const cloudConnected = ref(false);
const environmentLoading = ref(false);
const refreshEnvironment = vi.fn(async () => undefined);
const effectiveActiveSet = ref<Record<string, unknown> | null>({ id: 'workproba-cloud' });
const sidecarState = ref<'connected' | 'idle' | 'working' | 'error'>('idle');

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

vi.mock('@composables/useChatActivity', () => ({
  useChatActivity: () => ({
    sidecarState,
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    effectiveActiveSet,
  }),
}));

vi.mock('@composables/useOrganizationEnvironment', () => ({
  useOrganizationEnvironment: () => ({
    organizationName,
    cloudConnected,
    loading: environmentLoading,
    refresh: refreshEnvironment,
  }),
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
  it('affiche un environnement local quand aucune organisation n’est connectée', () => {
    organizationName.value = null;
    cloudConnected.value = false;
    effectiveActiveSet.value = { id: 'workproba-cloud' };

    const wrapper = mountTitleBar();

    expect(wrapper.find('.wp-titlebar__chip-label').text()).toBe('Environnement local');
    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--idle');
  });

  it('affiche une erreur quand aucun moteur effectif n’est configuré', () => {
    organizationName.value = null;
    cloudConnected.value = false;
    effectiveActiveSet.value = null;
    sidecarState.value = 'connected';

    const wrapper = mountTitleBar();

    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--error');
  });

  it('affiche une erreur sidecar dans le tooltip', () => {
    organizationName.value = 'Improba';
    cloudConnected.value = true;
    effectiveActiveSet.value = { id: 'workproba-cloud' };
    sidecarState.value = 'error';

    const wrapper = mountTitleBar();

    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--error');
    expect(wrapper.find('.wp-titlebar__chip').attributes('aria-label')).toContain('Service IA injoignable');
  });

  it('affiche le nom de l’organisation et ouvre son environnement', async () => {
    organizationName.value = 'Improba';
    cloudConnected.value = true;
    effectiveActiveSet.value = { id: 'workproba-cloud' };
    sidecarState.value = 'connected';

    const wrapper = mountTitleBar();

    expect(wrapper.find('.wp-titlebar__chip-label').text()).toBe('Improba');
    expect(wrapper.find('.wp-titlebar__chip').classes()).toContain('wp-titlebar__chip--connected');

    await wrapper.find('.wp-titlebar__chip').trigger('click');
    expect(wrapper.emitted('toggle-environment')).toHaveLength(1);
  });

  it('navigue vers l\'accueil au clic sur Workproba', async () => {
    push.mockClear();

    const wrapper = mountTitleBar({
      workspaceTitle: 'kaggle',
      activePath: '/tmp/kaggle',
    });

    await wrapper.find('.wp-titlebar__mark').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'home' });
  });
});
