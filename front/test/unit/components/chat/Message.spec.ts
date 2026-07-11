import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import Message from '@components/chat/Message.vue';

describe('Message accessibilité', () => {
  it('affiche un libellé de rôle visible pour le message user', () => {
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

    const roleLabel = user.find('.chat-message__role');
    expect(roleLabel.exists()).toBe(true);
    expect(roleLabel.isVisible()).toBe(true);
    expect(roleLabel.text()).toBe('Vous');
    user.unmount();
  });

  it('affiche un libellé de rôle visible pour le message assistant', () => {
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

    const roleLabel = assistant.find('.chat-message__role');
    expect(roleLabel.exists()).toBe(true);
    expect(roleLabel.isVisible()).toBe(true);
    expect(roleLabel.text()).toBe('Assistant');
    assistant.unmount();
  });

  it('associe le libellé de rôle visible à l’article via aria-labelledby', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'u2',
          role: 'user',
          content: 'Test',
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

    const article = wrapper.find('article.chat-message');
    expect(article.attributes('aria-labelledby')).toBe('chat-message-role-u2');
    expect(wrapper.find('#chat-message-role-u2').text()).toBe('Vous');
    wrapper.unmount();
  });
});
