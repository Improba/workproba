import { ref } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LockedModelSetup from '@components/settings/LockedModelSetup.vue';
import { WORKPROBA_CLOUD_BUILTIN_SET } from '@utils/providerSets';

const mockInitCloud = vi.fn().mockResolvedValue(undefined);
const mockRefreshQuota = vi.fn().mockResolvedValue(undefined);
const mockIsEnrolled = ref(false);
const mockActiveSet = ref(WORKPROBA_CLOUD_BUILTIN_SET);
const mockSettings = ref({ supportEmail: null as string | null });

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    isEnrolled: mockIsEnrolled,
    init: mockInitCloud,
    refreshQuota: mockRefreshQuota,
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    activeSet: mockActiveSet,
    settings: mockSettings,
  }),
}));

vi.mock('@components/cloud/EnrollCloudModal.vue', () => ({
  default: {
    name: 'EnrollCloudModal',
    template: '<div data-testid="enroll-modal" />',
    props: ['modelValue'],
    emits: ['update:modelValue', 'enrolled'],
  },
}));

describe('LockedModelSetup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsEnrolled.value = false;
    mockActiveSet.value = WORKPROBA_CLOUD_BUILTIN_SET;
    mockSettings.value = { supportEmail: null };
  });

  function mountSetup() {
    return mount(LockedModelSetup, {
      global: {
        stubs: {
          Lucide: true,
        },
      },
    });
  }

  it('affiche le CTA enroll pour workproba-cloud non enrollé', () => {
    const wrapper = mountSetup();
    expect(wrapper.text()).toContain('Lier ce poste');
    expect(wrapper.find('.locked-setup__request--primary').exists()).toBe(true);
  });

  it('ouvre EnrollCloudModal au clic sur Lier ce poste', async () => {
    const wrapper = mountSetup();
    await wrapper.find('.locked-setup__request--primary').trigger('click');
    expect(wrapper.find('[data-testid="enroll-modal"]').exists()).toBe(true);
  });

  it('affiche Demander l\'accès quand le moteur n\'est pas cloud', () => {
    mockActiveSet.value = {
      ...WORKPROBA_CLOUD_BUILTIN_SET,
      id: 'mistral-default',
      authMode: 'api_key',
    };
    const wrapper = mountSetup();
    expect(wrapper.text()).toContain('Demander l\'accès');
    expect(wrapper.find('.locked-setup__request--primary').exists()).toBe(false);
  });

  it('initialise le cloud au montage', async () => {
    mountSetup();
    expect(mockInitCloud).toHaveBeenCalled();
  });
});
