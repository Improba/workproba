import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import ThinkingCard from '@components/chat/ThinkingCard.vue';

const thinkingDetailView = ref<'summary' | 'raw'>('summary');
const setThinkingDetailView = vi.fn(async (view: 'summary' | 'raw') => {
  thinkingDetailView.value = view;
});

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    thinkingDetailView,
    setThinkingDetailView,
  }),
}));

describe('ThinkingCard', () => {
  it('affiche le subject en en-tête quand disponible', () => {
    const wrapper = mount(ThinkingCard, {
      props: {
        thinking: {
          type: 'thinking',
          id: 'think-part-1',
          thinkingId: 'think-0',
          content: 'Contenu brut',
          done: true,
          subject: 'Vérifier la configuration',
          summary: 'Étape A · Étape B',
        },
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
        },
      },
    });

    expect(wrapper.find('[data-testid="thinking-card__subject"]').text()).toBe(
      'Vérifier la configuration',
    );
    wrapper.unmount();
  });

  it('affiche le résumé par défaut quand déplié', async () => {
    const wrapper = mount(ThinkingCard, {
      props: {
        thinking: {
          type: 'thinking',
          id: 'think-part-2',
          thinkingId: 'think-0',
          content: 'Contenu brut',
          done: true,
          subject: 'Synthèse',
          summary: 'Étape A · Étape B',
        },
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
        },
      },
    });

    await wrapper.find('.thinking-card__header').trigger('click');

    expect(wrapper.find('[data-testid="thinking-card__summary"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="thinking-card__summary"]').text()).toContain(
      'Étape A · Étape B',
    );
    wrapper.unmount();
  });

  it('bascule vers le détail brut via la préférence globale', async () => {
    thinkingDetailView.value = 'summary';
    setThinkingDetailView.mockClear();

    const wrapper = mount(ThinkingCard, {
      props: {
        thinking: {
          type: 'thinking',
          id: 'think-part-3',
          thinkingId: 'think-0',
          content: 'Ligne 1\nLigne 2',
          done: true,
          summary: 'Résumé court',
        },
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
        },
      },
    });

    await wrapper.find('.thinking-card__header').trigger('click');
    const toggle = wrapper.find('[data-testid="thinking-card__view-toggle"]');
    const buttons = toggle.findAll('button');
    await buttons[1]!.trigger('click');

    expect(setThinkingDetailView).toHaveBeenCalledWith('raw');
    wrapper.unmount();
  });

  it('expose aria-live et aria-busy sur le subject pendant le streaming', () => {
    const wrapper = mount(ThinkingCard, {
      props: {
        thinking: {
          type: 'thinking',
          id: 'think-part-stream',
          thinkingId: 'think-0',
          content: 'En cours',
          done: false,
          subject: 'Analyse',
        },
        streaming: true,
      },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
        },
      },
    });

    const subject = wrapper.find('[data-testid="thinking-card__subject"]');
    expect(subject.attributes('aria-live')).toBe('polite');
    expect(subject.attributes('aria-busy')).toBe('true');
    wrapper.unmount();
  });

  it('relie le bouton header à la région corps via aria-controls', async () => {
    const wrapper = mount(ThinkingCard, {
      props: {
        thinking: {
          type: 'thinking',
          id: 'think-part-a11y',
          thinkingId: 'think-0',
          content: 'Contenu',
          done: true,
          summary: 'Résumé',
        },
        streaming: false,
      },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
        },
      },
    });

    await wrapper.find('.thinking-card__header').trigger('click');

    const header = wrapper.find('.thinking-card__header');
    const bodyId = header.attributes('aria-controls');
    expect(bodyId).toBe('thinking-card-body-think-part-a11y');
    expect(wrapper.find(`#${bodyId}`).exists()).toBe(true);
    wrapper.unmount();
  });
});
