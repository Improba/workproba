import { describe, expect, it, vi } from 'vitest';
import { shallowMount, flushPromises } from '@vue/test-utils';
import { ref } from 'vue';
import IndexPage from '../../../src/pages/Index.vue';
import ErrorNotFoundPage from '../../../src/pages/ErrorNotFound.vue';

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@composables/useProject', () => ({
  useProject: () => ({
    activePath: ref<string | null>(null),
    activeWorkspaceId: ref<string | null>(null),
    loading: ref(false),
    error: ref<string | null>(null),
    openFolder: vi.fn(),
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    onboardingDone: ref(true),
    loaded: ref(true),
    setOnboardingDone: vi.fn(),
  }),
}));

vi.mock('@composables/useUserProfile', () => ({
  useUserProfile: () => ({
    needsOnboarding: ref(false),
    completeOnboarding: vi.fn(),
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  listWorkspaces: vi.fn(async () => []),
}));

vi.mock('@services/workspaceSession', () => ({
  createSession: vi.fn(),
  listSessions: vi.fn(async () => []),
}));

const HomeModule = () => import('../../../src/pages/Home.vue');

describe('pages smoke tests', () => {
  it('Index monte WorkprobaLayout et rend le router-view', () => {
    const wrapper = shallowMount(IndexPage, {
      global: {
        stubs: {
          WorkprobaLayout: { template: '<div class="layout-stub"><slot /></div>' },
          'router-view': { template: '<div class="router-view-stub" />' },
        },
      },
    });

    expect(wrapper.find('.layout-stub').exists()).toBe(true);
    expect(wrapper.find('.router-view-stub').exists()).toBe(true);
  });

  it('Home affiche l\'onboarding quand aucun dossier n\'est ouvert', async () => {
    const { default: HomePage } = await HomeModule();

    const wrapper = shallowMount(HomePage, {
      global: {
        stubs: {
          OpenFolderButton: { template: '<button class="open-folder" />' },
          StartPrompts: true,
          Lucide: true,
          'q-dialog': { template: '<div><slot /></div>' },
        },
      },
    });

    await flushPromises();

    expect(wrapper.text()).toContain('Bienvenue sur Workproba');
    expect(wrapper.find('.open-folder').exists()).toBe(true);
  });

  it('ErrorNotFound affiche le contenu 404', () => {
    const wrapper = shallowMount(ErrorNotFoundPage, {
      global: {
        stubs: {
          'router-link': { template: '<a><slot /></a>' },
          Lucide: true,
        },
      },
    });

    expect(wrapper.text()).toContain('404');
    expect(wrapper.text()).toContain('Page introuvable');
    expect(wrapper.text()).toContain('Retour à l\'accueil');
  });
});
