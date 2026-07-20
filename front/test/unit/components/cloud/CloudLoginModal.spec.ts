import { ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CloudLoginModal from '@components/cloud/CloudLoginModal.vue';

const mockLoginDesktopCloud = vi.fn();
const mockEnroll = vi.fn();
const mockRefreshStatus = vi.fn().mockResolvedValue(undefined);
const mockRefreshQuota = vi.fn().mockResolvedValue(undefined);
const mockSaveProfile = vi.fn();
const mockStatus = ref({
  enrolled: false,
  base_url: null as string | null,
  org_label: 'Acme Cloud',
});
const mockLoading = ref(false);
const mockLoadError = ref<string | null>(null);
const mockProfile = ref({ name: '', organisation: '' });
const mockNotifyCreate = vi.hoisted(() => vi.fn());

vi.mock('@services/cloudDesktopAuth', () => ({
  loginDesktopCloud: (...args: unknown[]) => mockLoginDesktopCloud(...args),
  displayNameFromUsername: (username: string) => username.split('@')[0],
  CloudDesktopAuthError: class CloudDesktopAuthError extends Error {
    status?: number;
    constructor(message: string, status?: number) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settings: ref({ cloudEndpoint: 'https://cloud.preset.test' }),
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    status: mockStatus,
    loading: mockLoading,
    loadError: mockLoadError,
    enroll: mockEnroll,
    refreshStatus: mockRefreshStatus,
    refreshQuota: mockRefreshQuota,
  }),
}));

vi.mock('@composables/useUserProfile', () => ({
  useUserProfile: () => ({
    profile: mockProfile,
    save: mockSaveProfile,
  }),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) =>
      key === 'cloud.loginUnreachable'
        ? 'Serveur cloud injoignable. Vérifiez l\'URL.'
        : key,
    te: (key: string) => key.startsWith('cloud.'),
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: mockNotifyCreate },
}));

function mountModal(open = true) {
  return mount(CloudLoginModal, {
    props: { modelValue: open },
    global: {
      stubs: {
        Lucide: true,
        QDialog: {
          template: '<div><slot /></div>',
          props: ['modelValue'],
        },
      },
    },
  });
}

describe('CloudLoginModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoading.value = false;
    mockLoadError.value = null;
    mockProfile.value = { name: '', organisation: '' };
    mockStatus.value = { enrolled: false, base_url: null, org_label: 'Acme Cloud' };
    mockLoginDesktopCloud.mockResolvedValue({ token: 'jwt-user' });
    mockEnroll.mockResolvedValue(true);
  });

  it('submit appelle login puis enroll', async () => {
    const wrapper = mountModal(true);

    await wrapper.find('#cloud-login-username').setValue('alice@org.test');
    await wrapper.find('#cloud-login-password').setValue('secret');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(mockLoginDesktopCloud).toHaveBeenCalledWith({
      baseUrl: 'https://cloud.preset.test',
      username: 'alice@org.test',
      password: 'secret',
    });
    expect(mockEnroll).toHaveBeenCalledWith({
      baseUrl: 'https://cloud.preset.test',
      bearerToken: 'jwt-user',
    });
    expect(mockRefreshStatus).toHaveBeenCalled();
    expect(mockRefreshQuota).toHaveBeenCalled();
    expect(mockSaveProfile).toHaveBeenCalledWith({
      name: 'alice',
      organisation: 'Acme Cloud',
    });
    expect(wrapper.emitted('enrolled')).toHaveLength(1);
    expect(wrapper.emitted('success')).toHaveLength(1);
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false]);
  });

  it('émet open-invitation depuis le lien discret', async () => {
    const wrapper = mountModal(true);

    await wrapper.find('.cloud-login-modal__invitation').trigger('click');

    expect(wrapper.emitted('open-invitation')).toHaveLength(1);
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false]);
  });

  it('traduit les clés camelCase d\'erreur auth', async () => {
    const { CloudDesktopAuthError } = await import('@services/cloudDesktopAuth');
    mockLoginDesktopCloud.mockRejectedValue(
      new CloudDesktopAuthError('cloud.loginUnreachable'),
    );

    const wrapper = mountModal(true);
    await wrapper.find('#cloud-login-username').setValue('admin@improba.fr');
    await wrapper.find('#cloud-login-password').setValue('secret');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('.cloud-login-modal__error').text()).toBe(
      'Serveur cloud injoignable. Vérifiez l\'URL.',
    );
    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Serveur cloud injoignable. Vérifiez l\'URL.',
        color: 'negative',
      }),
    );
  });
});
