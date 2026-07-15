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

  it('affiche le bouton copier pour une réponse assistant terminée', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-copy',
          role: 'assistant',
          content: 'Réponse copiable',
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

    const actions = wrapper.findAll('.chat-message__action');
    const copyBtn = actions.find((btn) => btn.text().includes('Copier'));
    expect(copyBtn).toBeTruthy();
    expect(copyBtn!.text()).toContain('Copier');
    wrapper.unmount();
  });

  it('affiche modifier sur un message user terminé', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'u-edit',
          role: 'user',
          content: 'Question initiale',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        chatStreaming: false,
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

    expect(wrapper.text()).toContain('Modifier');
    wrapper.unmount();
  });

  it('affiche regénérer sur une réponse assistant terminée', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-regen',
          role: 'assistant',
          content: 'Réponse',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        chatStreaming: false,
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

    expect(wrapper.text()).toContain('Regénérer');
    wrapper.unmount();
  });

  it('émet edit après enregistrement du brouillon', async () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'u-save',
          role: 'user',
          content: 'Ancien texte',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        chatStreaming: false,
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

    await wrapper.find('.chat-message__action').trigger('click');
    const textarea = wrapper.find('.chat-message__edit-field');
    await textarea.setValue('Nouveau texte');
    await wrapper.find('.chat-message__action--primary').trigger('click');

    expect(wrapper.emitted('edit')).toEqual([['u-save', 'Nouveau texte']]);
    wrapper.unmount();
  });

  it('masque le bouton copier pendant le streaming', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-stream',
          role: 'assistant',
          content: 'En cours…',
          streaming: true,
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

    expect(wrapper.find('.chat-message__action').exists()).toBe(false);
    wrapper.unmount();
  });

  it('utilise ThinkingCard comme placeholder de raisonnement initial', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-think',
          role: 'assistant',
          content: '',
          streaming: true,
          parts: [],
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      },
      global: {
        stubs: {
          Lucide: true,
          MessageTextPart: { template: '<div class="text-part" />' },
          ThinkingCard: {
            props: ['thinking', 'streaming'],
            template: '<div class="thinking-card-stub" />',
          },
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    expect(wrapper.find('.thinking-card-stub').exists()).toBe(true);
    expect(wrapper.find('.chat-message__thinking-placeholder').exists()).toBe(false);
    wrapper.unmount();
  });
});
