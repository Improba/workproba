import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ToolCallCard from '@components/chat/ToolCallCard.vue';
import type { ChatToolCall } from '#types';

vi.mock('@composables/useToolCallExpansion', () => ({
  useToolCallExpansion: () => ({
    isTechView: { value: false },
    showRaw: { value: false },
    toggleTechView: vi.fn(),
    toggleRaw: vi.fn(),
  }),
}));

function tc(over: Partial<ChatToolCall> = {}): ChatToolCall {
  return {
    id: 'tc1',
    name: 'write_pptx',
    status: 'success',
    startedAt: 1,
    filePath: 'decks/pitch.pptx',
    args: { path: 'decks/pitch.pptx' },
    ...over,
  };
}

describe('ToolCallCard fichier pptx', () => {
  it('affiche le bouton fichier après succès', async () => {
    const wrapper = mount(ToolCallCard, {
      props: { toolCall: tc({ status: 'success' }) },
      global: { stubs: { Lucide: true, 'q-spinner': true } },
    });
    await flushPromises();
    expect(wrapper.find('.tool-call-card__file-btn').exists()).toBe(true);
    expect(wrapper.find('.tool-call-card__file-btn').text()).toContain('pitch.pptx');
    wrapper.unmount();
  });

  it('masque le bouton fichier pendant la confirmation (fichier pas encore écrit)', async () => {
    const wrapper = mount(ToolCallCard, {
      props: {
        toolCall: tc({ status: 'awaiting_confirmation' }),
        confirmationActive: true,
      },
      global: { stubs: { Lucide: true, 'q-spinner': true } },
    });
    await flushPromises();
    expect(wrapper.find('.tool-call-card__file-btn').exists()).toBe(false);
    wrapper.unmount();
  });
});
