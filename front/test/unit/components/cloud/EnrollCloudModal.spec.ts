import { ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import EnrollCloudModal from '@components/cloud/EnrollCloudModal.vue';
import EnrollCloudJoinForm from '@components/cloud/EnrollCloudJoinForm.vue';

const mockEnroll = vi.fn();
const mockRefreshStatus = vi.fn().mockResolvedValue(undefined);
const mockRefreshQuota = vi.fn().mockResolvedValue(undefined);
const mockStatus = ref({
  enrolled: false,
  base_url: null as string | null,
});
const mockLoading = ref(false);
const mockLoadError = ref<string | null>(null);
const mockNotifyCreate = vi.hoisted(() => vi.fn());

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

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('quasar', () => ({
  Notify: { create: mockNotifyCreate },
}));

function mountModal(open = true) {
  return mount(EnrollCloudModal, {
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

describe('EnrollCloudModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoading.value = false;
    mockLoadError.value = null;
    mockStatus.value = { enrolled: false, base_url: null };
    mockEnroll.mockResolvedValue(true);
  });

  it('affiche le formulaire join quand ouvert', () => {
    const wrapper = mountModal(true);
    expect(wrapper.text()).toContain('cloud.joinTitle');
    expect(wrapper.findComponent(EnrollCloudJoinForm).exists()).toBe(true);
  });

  it('émet enrolled et ferme après un join réussi', async () => {
    const wrapper = mountModal(true);
    await wrapper.find('#cloud-join-token').setValue('invite-abc');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(mockEnroll).toHaveBeenCalledWith({
      baseUrl: 'https://cloud.preset.test',
      joinToken: 'invite-abc',
      bearerToken: undefined,
    });
    expect(mockRefreshStatus).toHaveBeenCalled();
    expect(mockRefreshQuota).toHaveBeenCalled();
    expect(wrapper.emitted('enrolled')).toHaveLength(1);
    expect(wrapper.emitted('success')).toHaveLength(1);
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false]);
    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'cloud.joinSuccess', color: 'positive' }),
    );
  });

  it('notifie en cas d\'échec d\'enrollment', async () => {
    mockEnroll.mockResolvedValue(false);
    mockLoadError.value = 'invalid_join_token';

    const wrapper = mountModal(true);
    await wrapper.find('#cloud-join-token').setValue('bad');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.emitted('enrolled')).toBeUndefined();
    expect(mockNotifyCreate).toHaveBeenCalledWith(
      expect.objectContaining({ color: 'negative' }),
    );
  });

  it('émet cancel à la fermeture', async () => {
    const wrapper = mountModal(true);
    await wrapper.find('.enroll-cloud-modal__cancel').trigger('click');
    expect(wrapper.emitted('cancel')).toHaveLength(1);
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false]);
  });
});

describe('EnrollCloudJoinForm', () => {
  it('désactive le submit sans code d\'invitation', () => {
    const wrapper = mount(EnrollCloudJoinForm, {
      props: {
        joinToken: '',
        showUrlField: false,
      },
    });

    const submit = wrapper.find('button[type="submit"]');
    expect((submit.element as HTMLButtonElement).disabled).toBe(true);
  });

  it('émet submit avec token renseigné', async () => {
    const wrapper = mount(EnrollCloudJoinForm, {
      props: {
        joinToken: 'invite-1',
        showUrlField: false,
      },
    });

    await wrapper.find('form').trigger('submit');
    expect(wrapper.emitted('submit')).toHaveLength(1);
  });
});
