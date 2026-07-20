import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ChatView from '@components/chat/ChatView.vue';
import MessageList from '@components/chat/MessageList.vue';

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
});
