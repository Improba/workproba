import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import ChatView from '@components/chat/ChatView.vue';
import MessageList from '@components/chat/MessageList.vue';

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
  }),
}));

vi.mock('@components/cloud/EnrollCloudModal.vue', () => ({
  default: { template: '<div />' },
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe('ChatView accessibilité', () => {
  it('délègue role=log et aria-live au conteneur scrollable des messages', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: 'Bonjour',
            createdAt: '2026-01-01T00:00:00.000Z',
          },
        ],
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          ChatModelMenuContent: true,
          MessageList: false,
        },
      },
    });

    const list = wrapper.findComponent(MessageList);
    const scroller = list.find('.message-list__scroller');
    expect(scroller.attributes('role')).toBe('log');
    expect(scroller.attributes('aria-live')).toBe('polite');
    expect(scroller.attributes('aria-relevant')).toBe('additions');
  });

  it('affiche une bannière moteur quand aucun set effectif', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [],
        streaming: false,
        settingsLocked: false,
      },
      global: {
        stubs: {
          Lucide: true,
          ChatModelMenuContent: true,
          StartPrompts: true,
          EnrollCloudModal: true,
        },
      },
    });

    expect(wrapper.find('.chat-view__engine-banner').exists()).toBe(true);
    expect(wrapper.find('.chat-view__engine-banner-action').exists()).toBe(true);
  });

  it('masque la bannière moteur si settings verrouillés', () => {
    const wrapper = mount(ChatView, {
      props: {
        messages: [],
        streaming: false,
        settingsLocked: true,
      },
      global: {
        stubs: {
          Lucide: true,
          ChatModelMenuContent: true,
          StartPrompts: true,
          EnrollCloudModal: true,
        },
      },
    });

    expect(wrapper.find('.chat-view__engine-banner').exists()).toBe(false);
  });
});
