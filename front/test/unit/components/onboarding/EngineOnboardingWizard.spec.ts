import { ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import EngineOnboardingWizard from '@components/onboarding/EngineOnboardingWizard.vue';

const mockSetActiveSet = vi.fn().mockResolvedValue(undefined);
const mockSetOnboardingDone = vi.fn().mockResolvedValue(undefined);
const mockUpdateSet = vi.fn().mockResolvedValue(undefined);
const mockLoad = vi.fn().mockResolvedValue(undefined);
const mockInitCloud = vi.fn().mockResolvedValue(undefined);
const mockRefreshQuota = vi.fn().mockResolvedValue(undefined);
const mockSaveProfile = vi.fn();
const mockProfile = ref({ name: '', organisation: '' });
const cloudStatus = ref<{ enrolled: boolean; org_label?: string | null } | null>({
  enrolled: true,
  org_label: 'Acme Cloud',
});

const desktopMocks = vi.hoisted(() => ({
  openExternalUrl: vi.fn().mockResolvedValue(undefined),
}));

const mistralSet = {
  id: 'mistral-default',
  name: 'Mistral',
  isBuiltin: true,
  chat: { provider: 'mistral', model: 'mistral-medium-latest', apiKey: null },
  embeddings: null,
  capabilities: {},
  vision: { mode: 'none' },
  ocr: { mode: 'none' },
};

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    sets: ref([mistralSet]),
    load: mockLoad,
    setActiveSet: mockSetActiveSet,
    updateSet: mockUpdateSet,
    setOnboardingDone: mockSetOnboardingDone,
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: cloudStatus,
    providerReadiness: ref({ enrolled: true, reachable: true }),
    init: mockInitCloud,
    refreshQuota: mockRefreshQuota,
  }),
}));

vi.mock('@composables/useUserProfile', () => ({
  useUserProfile: () => ({
    profile: mockProfile,
    save: mockSaveProfile,
  }),
}));

vi.mock('@composables/useDesktop', () => ({
  isDesktopApp: () => true,
  openExternalUrl: desktopMocks.openExternalUrl,
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: vi.fn() },
}));

function mountWizard() {
  return mount(EngineOnboardingWizard, {
    global: {
      stubs: {
        Lucide: true,
        QInput: {
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
          props: ['modelValue', 'label', 'type', 'outlined', 'dense'],
        },
        CloudLoginModal: {
          name: 'CloudLoginModal',
          template: '<div data-testid="cloud-login-modal-stub" />',
          props: ['modelValue'],
        },
        EnrollCloudModal: {
          name: 'EnrollCloudModal',
          template: '<div data-testid="enroll-modal-stub" />',
          props: ['modelValue', 'technical'],
        },
        ManualOpenAiCompatForm: {
          template: '<button data-testid="manual-activate" @click="$emit(\'activated\', \'custom-set\')">activate</button>',
        },
      },
    },
  });
}

describe('EngineOnboardingWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockProfile.value = { name: '', organisation: '' };
    cloudStatus.value = { enrolled: true, org_label: 'Acme Cloud' };
    mockSetActiveSet.mockResolvedValue(undefined);
    mockSetOnboardingDone.mockResolvedValue(undefined);
  });

  it('affiche les 3 branches principales', () => {
    const wrapper = mountWizard();

    expect(wrapper.find('[data-testid="engine-onboarding-login"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="engine-onboarding-register"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="engine-onboarding-api-key"]').exists()).toBe(true);
  });

  it('branche clé d\'accès : mistral et manuel visibles', async () => {
    const wrapper = mountWizard();

    await wrapper.find('[data-testid="engine-onboarding-api-key"]').trigger('click');

    expect(wrapper.find('[data-testid="engine-onboarding-mistral"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="engine-onboarding-manual"]').exists()).toBe(true);
  });

  it('active Mistral puis persiste onboardingDone', async () => {
    const wrapper = mountWizard();

    await wrapper.find('[data-testid="engine-onboarding-api-key"]').trigger('click');
    await wrapper.find('[data-testid="engine-onboarding-mistral"]').trigger('click');
    await wrapper.find('input').setValue('sk-mistral-test');
    await wrapper.find('[data-testid="engine-onboarding-mistral-submit"]').trigger('click');
    await flushPromises();

    expect(mockUpdateSet).toHaveBeenCalled();
    expect(mockSetActiveSet).toHaveBeenCalledWith(
      'mistral-default',
      expect.objectContaining({ cloud: expect.anything() }),
    );
    expect(mockSetOnboardingDone).toHaveBeenCalledWith(true);
    expect(wrapper.emitted('complete')).toHaveLength(1);
  });

  it('configuration manuelle émet complete et persiste onboardingDone', async () => {
    const wrapper = mountWizard();

    await wrapper.find('[data-testid="engine-onboarding-api-key"]').trigger('click');
    await wrapper.find('[data-testid="engine-onboarding-manual"]').trigger('click');
    await wrapper.find('[data-testid="manual-activate"]').trigger('click');
    await flushPromises();

    expect(mockSetOnboardingDone).toHaveBeenCalledWith(true);
    expect(wrapper.emitted('complete')).toHaveLength(1);
  });

  it('connexion cloud ouvre la modale identifiants', async () => {
    const wrapper = mountWizard();

    await wrapper.find('[data-testid="engine-onboarding-login"]').trigger('click');
    await flushPromises();

    expect(desktopMocks.openExternalUrl).not.toHaveBeenCalled();
    expect(wrapper.findComponent({ name: 'CloudLoginModal' }).props('modelValue')).toBe(true);
  });

  it('inscription cloud ouvre le navigateur puis propose le collage du code', async () => {
    const wrapper = mountWizard();

    await wrapper.find('[data-testid="engine-onboarding-register"]').trigger('click');
    await flushPromises();

    expect(desktopMocks.openExternalUrl).toHaveBeenCalledWith('http://localhost:8482/auth/register');
    expect(wrapper.find('[data-testid="engine-onboarding-paste-invitation"]').exists()).toBe(true);
  });

  it('après enroll cloud, synchronise org_label dans le profil', async () => {
    const wrapper = mountWizard();
    const modal = wrapper.findComponent({ name: 'CloudLoginModal' });

    await modal.vm.$emit('enrolled');
    await flushPromises();

    expect(mockRefreshQuota).toHaveBeenCalled();
    expect(mockSaveProfile).toHaveBeenCalledWith({ organisation: 'Acme Cloud' });
    expect(mockSetActiveSet).toHaveBeenCalledWith(
      'workproba-cloud',
      expect.objectContaining({ cloud: expect.anything() }),
    );
    expect(mockSetOnboardingDone).toHaveBeenCalledWith(true);
  });
});
