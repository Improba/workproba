import { ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SpaceSidebar from '@components/workproba/SpaceSidebar.vue';

const mockPush = vi.fn();
const onboardingDone = ref(false);
const cloudEnrolled = ref(false);
const cloudStatus = ref<{ org_label?: string | null; org_id?: string | null } | null>(null);
const profile = ref({ name: '', organisation: '' });

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ params: {}, name: 'home' }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
    locale: ref('fr'),
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

vi.mock('@composables/useSpace', () => ({
  useSpace: () => ({
    activePath: ref(null),
    activeSpaceId: ref(null),
    activeDataDir: ref(null),
    openSpace: vi.fn(),
    switchSpace: vi.fn(),
    renameSpace: vi.fn(),
    initFromStoredPath: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    onboardingDone,
  }),
}));

vi.mock('@composables/useUserProfile', () => ({
  useUserProfile: () => ({
    profile,
    initials: ref('?'),
    save: vi.fn(),
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: cloudStatus,
    isEnrolled: cloudEnrolled,
    init: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  listWorkspaces: vi.fn(async () => []),
}));

vi.mock('@composables/useSessionSync', () => ({
  bumpSessions: vi.fn(),
  useSessionSync: () => ({ sessionVersion: ref(0) }),
}));

vi.mock('@services/workspaceSession', () => ({
  createSession: vi.fn(),
  listSessions: vi.fn(async () => []),
}));

vi.mock('@composables/useMemoryPanel', () => ({
  useMemoryPanel: () => ({
    panelRequest: ref(null),
    clearMemoryPanelRequest: vi.fn(),
  }),
}));

function mountSidebar() {
  return mount(SpaceSidebar, {
    global: {
      stubs: {
        Lucide: true,
        MemoryPanel: true,
        SpaceSettingsDialog: true,
        CloudLoginModal: {
          name: 'CloudLoginModal',
          template: '<div data-testid="cloud-login-modal-stub" />',
          props: ['modelValue'],
        },
        EnrollCloudModal: {
          name: 'EnrollCloudModal',
          template: '<div data-testid="enroll-cloud-modal-stub" />',
          props: ['modelValue'],
        },
        'q-dialog': { template: '<div><slot /></div>' },
      },
    },
  });
}

describe('SpaceSidebar identity', () => {
  beforeEach(() => {
    onboardingDone.value = false;
    cloudEnrolled.value = false;
    cloudStatus.value = null;
    profile.value = { name: '', organisation: '' };
    mockPush.mockClear();
  });

  it('affiche l\'état invité avant onboarding moteur', () => {
    const wrapper = mountSidebar();

    expect(wrapper.find('.wp-sidebar__profile-name').text()).toBe('shell.guestName');
    expect(wrapper.find('.wp-sidebar__profile-org').text()).toBe('shell.guestOrg');
  });

  it('clic invité ouvre la modale de connexion cloud', async () => {
    const wrapper = mountSidebar();

    await wrapper.find('.wp-sidebar__profile').trigger('click');
    await flushPromises();

    expect(mockPush).not.toHaveBeenCalled();
    expect(wrapper.findComponent({ name: 'CloudLoginModal' }).props('modelValue')).toBe(true);
  });

  it('affiche l\'identité cloud après enroll', async () => {
    onboardingDone.value = true;
    cloudEnrolled.value = true;
    cloudStatus.value = { org_label: 'Org Cloud' };
    profile.value = { name: 'Alice', organisation: '' };

    const wrapper = mountSidebar();
    await flushPromises();

    expect(wrapper.find('.wp-sidebar__profile-name').text()).toBe('Alice');
    expect(wrapper.find('.wp-sidebar__profile-org').text()).toBe('Org Cloud');
  });

  it('affiche le mode local sans orga inventée', async () => {
    onboardingDone.value = true;
    cloudEnrolled.value = false;
    profile.value = { name: 'admin', organisation: 'Local Org' };

    const wrapper = mountSidebar();
    await flushPromises();

    expect(wrapper.find('.wp-sidebar__profile-name').text()).toBe('shell.localMode');
    expect(wrapper.find('.wp-sidebar__profile-org').text()).toBe('shell.connectPrompt');
    expect(wrapper.find('.wp-sidebar__profile-name').text()).not.toBe('admin');
  });

  it('clic non connecté ouvre la modale de connexion cloud', async () => {
    onboardingDone.value = true;
    cloudEnrolled.value = false;

    const wrapper = mountSidebar();
    await wrapper.find('.wp-sidebar__profile').trigger('click');
    await flushPromises();

    expect(wrapper.findComponent({ name: 'CloudLoginModal' }).props('modelValue')).toBe(true);
  });
});
