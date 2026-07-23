import { mount } from '@vue/test-utils';
import { nextTick, reactive } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import Message from '@components/chat/Message.vue';
import * as expansion from '@composables/useToolCallExpansion';

describe('Message accessibilité', () => {
  it('affiche un libellé de rôle sr-only pour le message user', () => {
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
    expect(roleLabel.classes()).toContain('wp-sr-only');
    expect(roleLabel.text()).toBe('Vous');
    user.unmount();
  });

  it('affiche un libellé de rôle sr-only pour le message assistant', () => {
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
    expect(roleLabel.classes()).toContain('wp-sr-only');
    expect(roleLabel.text()).toBe('Assistant');
    assistant.unmount();
  });

  it('associe le libellé de rôle sr-only à l’article via aria-labelledby', () => {
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

  it('associe aria-labelledby au libellé sr-only pour un message compaction', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'compact-1',
          role: 'user',
          content: 'Résumé des échanges précédents :\n\nContenu résumé',
          messageKind: 'compaction',
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
    expect(article.attributes('aria-labelledby')).toBe('chat-message-role-compact-1');
    const roleLabel = wrapper.find('#chat-message-role-compact-1');
    expect(roleLabel.exists()).toBe(true);
    expect(roleLabel.classes()).toContain('wp-sr-only');
    expect(roleLabel.text()).toBe('Résumé de conversation');
    const card = wrapper.find('.chat-message__compaction-card');
    expect(card.exists()).toBe(true);
    expect(card.attributes('aria-label')).toBeUndefined();
    expect(card.attributes('role')).toBeUndefined();
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

  it('n’affiche pas modifier sur un message user', () => {
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

    expect(wrapper.text()).not.toContain('Modifier');
    expect(wrapper.find('.chat-message__actions').exists()).toBe(false);
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

  it('n’affiche pas de part texte vide pendant le raisonnement (replié ou non)', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-empty-text-thinking',
          role: 'assistant',
          content: '',
          streaming: true,
          parts: [
            { type: 'text', id: 'empty-text', content: '' },
            {
              type: 'thinking',
              id: 'think-part',
              thinkingId: 'think-0',
              content: 'Je réfléchis…',
              done: false,
            },
          ],
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

    expect(wrapper.find('.text-part').exists()).toBe(false);
    expect(wrapper.find('.thinking-card-stub').exists()).toBe(true);
    wrapper.unmount();
  });

  it('affiche les citations mémoire sur un message assistant', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-mem',
          role: 'assistant',
          content: 'Réponse avec mémoire.',
          memoryCitations: [
            {
              id: 'mem-42',
              snippet: 'Budget validé.',
              source: 'agent',
              scope: 'project',
            },
          ],
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
          MemoryCitationsBar: {
            props: ['citations'],
            template: '<ul class="memory-citations-stub" />',
          },
        },
      },
    });

    expect(wrapper.find('.memory-citations-stub').exists()).toBe(true);
    wrapper.unmount();
  });

  it('affiche les sources web sur un message assistant', () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-web',
          role: 'assistant',
          content: 'Réponse avec sources.',
          toolCalls: [
            {
              id: 'tc-web',
              name: 'web_search',
              status: 'success',
              args: { query: 'test' },
              result: {
                results: [
                  {
                    title: 'Example',
                    url: 'https://example.com/',
                    snippet: 'Snippet.',
                  },
                ],
              },
            },
          ],
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
          MemoryCitationsBar: true,
          WebSearchCitationsBar: {
            props: ['citations'],
            template: '<ul class="web-search-citations-stub" />',
          },
        },
      },
    });

    expect(wrapper.find('.web-search-citations-stub').exists()).toBe(true);
    wrapper.unmount();
  });

  it('replie le raisonnement quand un tool_call suit immédiatement', async () => {
    const collapseSpy = vi.spyOn(expansion, 'collapseThinking');

    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-thinking-tool',
          role: 'assistant',
          content: '',
          streaming: true,
          parts: [
            {
              type: 'thinking',
              id: 'think-part',
              thinkingId: 'think-0',
              content: 'Analyse en cours',
              done: false,
            },
          ],
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

    collapseSpy.mockClear();
    await wrapper.setProps({
      message: {
        id: 'a-thinking-tool',
        role: 'assistant',
        content: '',
        streaming: true,
        toolCalls: [
          { id: 'tc-1', name: 'list_files', status: 'running' },
        ],
        parts: [
          {
            type: 'thinking',
            id: 'think-part',
            thinkingId: 'think-0',
            content: 'Analyse en cours',
            done: false,
          },
          {
            type: 'tool_call',
            id: 'tc-part',
            toolCallId: 'tc-1',
          },
        ],
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    });

    expect(collapseSpy).toHaveBeenCalledWith('think-part');
    collapseSpy.mockRestore();
    wrapper.unmount();
  });

  it('replie le raisonnement quand un tool_call est ajouté in-place sur parts', async () => {
    const collapseSpy = vi.spyOn(expansion, 'collapseThinking');
    const message = reactive({
      id: 'a-inplace',
      role: 'assistant' as const,
      content: '',
      streaming: true,
      parts: [
        {
          type: 'thinking' as const,
          id: 'think-part',
          thinkingId: 'think-0',
          content: 'Analyse en cours',
          done: false,
        },
      ],
      createdAt: '2026-01-01T00:00:00.000Z',
    });

    const wrapper = mount(Message, {
      props: { message },
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

    collapseSpy.mockClear();
    message.parts.push({
      type: 'tool_call',
      id: 'tc-part',
      toolCallId: 'tc-1',
    });
    await nextTick();

    expect(collapseSpy).toHaveBeenCalledWith('think-part');
    collapseSpy.mockRestore();
    wrapper.unmount();
  });

  it('ne replie pas le raisonnement si un texte sépare thinking et tool_call', async () => {
    const collapseSpy = vi.spyOn(expansion, 'collapseThinking');

    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-thinking-text-tool',
          role: 'assistant',
          content: '',
          streaming: true,
          parts: [
            {
              type: 'thinking',
              id: 'think-part',
              thinkingId: 'think-0',
              content: 'Analyse en cours',
              done: false,
            },
            {
              type: 'text',
              id: 'text-part',
              content: 'Voici mon analyse.',
            },
          ],
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

    collapseSpy.mockClear();
    await wrapper.setProps({
      message: {
        id: 'a-thinking-text-tool',
        role: 'assistant',
        content: 'Voici mon analyse.',
        streaming: true,
        toolCalls: [
          { id: 'tc-1', name: 'list_files', status: 'running' },
        ],
        parts: [
          {
            type: 'thinking',
            id: 'think-part',
            thinkingId: 'think-0',
            content: 'Analyse en cours',
            done: false,
          },
          {
            type: 'text',
            id: 'text-part',
            content: 'Voici mon analyse.',
          },
          {
            type: 'tool_call',
            id: 'tc-part',
            toolCallId: 'tc-1',
          },
        ],
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    });

    expect(collapseSpy).not.toHaveBeenCalled();
    collapseSpy.mockRestore();
    wrapper.unmount();
  });
});

describe('Message erreur inline', () => {
  const defaultStubs = {
    Lucide: true,
    MessageTextPart: { template: '<div class="text-part" />' },
    ThinkingCard: true,
    ToolCallCard: true,
    ConfirmationCard: true,
  };

  it('affiche le bouton reconnect sur invalid_user_jwt et émet error-reconnect', async () => {
    const wrapper = mount(Message, {
      props: {
        message: {
          id: 'a-err',
          role: 'assistant',
          content: '',
          error: {
            message: 'Session expirée',
            code: 'invalid_user_jwt',
            retryable: false,
          },
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      },
      global: { stubs: defaultStubs },
    });

    const reconnectBtn = wrapper.find('.chat-message__error-reconnect');
    expect(reconnectBtn.exists()).toBe(true);
    expect(reconnectBtn.text()).toContain('Se reconnecter');
    await reconnectBtn.trigger('click');
    expect(wrapper.emitted('error-reconnect')).toEqual([['login']]);
    wrapper.unmount();
  });
});

describe('Message placeholder continuation', () => {
  const defaultStubs = {
    Lucide: true,
    MessageTextPart: { template: '<div class="text-part" />' },
    ThinkingCard: true,
    ToolCallCard: true,
    ConfirmationCard: true,
  };

  function mountStreamingToolsMessage(overrides: Record<string, unknown> = {}) {
    return mount(Message, {
      props: {
        message: {
          id: 'a-continuation',
          role: 'assistant',
          content: '',
          streaming: true,
          toolCalls: [{ id: 'tc-1', name: 'list_files', status: 'success' }],
          parts: [{ type: 'tool_call', id: 'tc-part', toolCallId: 'tc-1' }],
          createdAt: '2026-01-01T00:00:00.000Z',
          ...overrides,
        },
      },
      global: { stubs: defaultStubs },
    });
  }

  it('affiche le placeholder continuation quand tools terminaux et pas de texte', () => {
    const wrapper = mountStreamingToolsMessage();
    const placeholder = wrapper.find('.chat-message__continuation');

    expect(placeholder.exists()).toBe(true);
    expect(placeholder.text()).toContain('Suite de la génération');
    wrapper.unmount();
  });

  it('masque le placeholder continuation si un tool est encore running', () => {
    const wrapper = mountStreamingToolsMessage({
      toolCalls: [{ id: 'tc-1', name: 'list_files', status: 'running' }],
    });

    expect(wrapper.find('.chat-message__continuation').exists()).toBe(false);
    wrapper.unmount();
  });

  it('masque le placeholder continuation si du texte assistant est visible', () => {
    const wrapper = mountStreamingToolsMessage({
      content: 'Voici la suite.',
      parts: [
        { type: 'tool_call', id: 'tc-part', toolCallId: 'tc-1' },
        { type: 'text', id: 'text-part', content: 'Voici la suite.' },
      ],
    });

    expect(wrapper.find('.chat-message__continuation').exists()).toBe(false);
    wrapper.unmount();
  });

  it('masque le placeholder continuation quand streaming est terminé', () => {
    const wrapper = mountStreamingToolsMessage({ streaming: false });

    expect(wrapper.find('.chat-message__continuation').exists()).toBe(false);
    wrapper.unmount();
  });

  it('masque le placeholder continuation pendant une confirmation active', () => {
    const wrapper = mountStreamingToolsMessage({
      pendingConfirmation: {
        confirmationId: 'cf-1',
        toolCallId: 'tc-1',
        toolName: 'write_docx',
        action: 'create',
        proposedPath: 'out.docx',
        humanSummary: 'Créer',
      },
    });

    expect(wrapper.find('.chat-message__continuation').exists()).toBe(false);
    wrapper.unmount();
  });
});
