import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import ChatComposer from '@components/chat/ChatComposer.vue';

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    activeSet: ref(null),
    effectiveActiveSet: ref(null),
    effectiveActiveSetId: ref(null),
  }),
}));

vi.mock('@composables/useCloud', () => ({
  useCloud: () => ({
    isEnrolled: ref(false),
    init: vi.fn(),
    refreshQuota: vi.fn(),
    providerReadiness: ref({}),
  }),
}));

vi.mock('@components/cloud/EnrollCloudModal.vue', () => ({
  default: { template: '<div />' },
}));

vi.mock('@components/cloud/CloudLoginModal.vue', () => ({
  default: { template: '<div />' },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe('ChatComposer', () => {
  const defaultStubs = {
    Lucide: true,
    ChatModelMenuContent: true,
    ChatComposerAttachments: true,
    'q-input': true,
    'q-menu': true,
    'q-list': true,
    'q-item': true,
    'q-item-section': true,
    'q-item-label': true,
    'q-separator': true,
  };

  it('expose setDraft comme API publique', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        messages: [],
        streaming: false,
      },
      global: { stubs: defaultStubs },
    });

    expect(typeof (wrapper.vm as { setDraft?: unknown }).setDraft).toBe('function');
    wrapper.unmount();
  });

  it('affiche la bannière moteur quand aucun set effectif', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        messages: [],
        streaming: false,
        settingsLocked: false,
      },
      global: { stubs: defaultStubs },
    });

    expect(wrapper.find('.chat-composer__engine-banner').exists()).toBe(true);
    wrapper.unmount();
  });
});
