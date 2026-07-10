import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import Message from '@components/chat/Message.vue';

describe('Message accessibilité', () => {
  it('expose un label sr-only pour le rôle du message', () => {
    const user = mount(Message, {
      props: {
        message: {
          id: 'u1',
          role: 'user',
          content: 'Salut',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      },
      global: {
        stubs: {
          Lucide: true,
          MessageTextPart: { template: '<div class="text-part" />' },
          ThinkingCard: true,
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    expect(user.find('.sr-only').text()).toBe('Vous');
    user.unmount();

    const assistant = mount(Message, {
      props: {
        message: {
          id: 'a1',
          role: 'assistant',
          content: 'Bonjour',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      },
      global: {
        stubs: {
          Lucide: true,
          MessageTextPart: { template: '<div class="text-part" />' },
          ThinkingCard: true,
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    expect(assistant.find('.sr-only').text()).toBe('Assistant');
    assistant.unmount();
  });
});
