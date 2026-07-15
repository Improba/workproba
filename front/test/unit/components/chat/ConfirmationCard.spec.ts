import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import ConfirmationCard from '@components/chat/ConfirmationCard.vue';
import type { ChatConfirmation } from '#types';

function baseConfirmation(overrides: Partial<ChatConfirmation> = {}): ChatConfirmation {
  return {
    confirmationId: 'cf_1',
    toolCallId: 'tc_1',
    toolName: 'generate_document',
    action: 'create',
    proposedPath: 'note.docx',
    humanSummary: 'Je vais créer note.docx',
    ...overrides,
  };
}

describe('ConfirmationCard', () => {
  it('affiche le rendu orienté effet quand headline est présent', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          headline: 'Je vais Créer : Note.docx',
          protectionLabels: [
            'Aperçu disponible avant validation',
            'Aucun accès réseau',
          ],
        }),
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('[data-testid="confirmation-card"]').exists()).toBe(true);
    expect(wrapper.find('.confirmation-card__headline').text()).toBe(
      'Je vais Créer : Note.docx',
    );
    expect(wrapper.find('.confirmation-card__headline-target').text()).toBe('Note.docx');
    const protections = wrapper.findAll('[data-testid="confirmation-protections"] li');
    expect(protections).toHaveLength(2);
    expect(protections[0].text()).toBe('Aperçu disponible avant validation');
    expect(protections[1].text()).toBe('Aucun accès réseau');
    expect(wrapper.find('.confirmation-card__summary').exists()).toBe(false);

    expect(wrapper.find('.confirmation-card__btn--deny').text()).toBe('Refuser');
    expect(wrapper.find('.confirmation-card__btn--approve').text()).toBe('Approuver');
    wrapper.unmount();
  });

  it('affiche le rendu legacy quand headline est vide', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          headline: '',
          humanSummary: '',
        }),
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('.confirmation-card__headline').exists()).toBe(false);
    expect(wrapper.find('.confirmation-card__summary').exists()).toBe(true);
    expect(wrapper.find('.confirmation-card__file').text()).toBe('note.docx');

    expect(wrapper.find('.confirmation-card__btn--deny').exists()).toBe(true);
    expect(wrapper.find('.confirmation-card__btn--approve').exists()).toBe(true);
    wrapper.unmount();
  });

  it('affiche le bouton preview quand les conditions sont remplies', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          toolName: 'write_docx',
          headline: 'Je vais Créer : note.docx',
        }),
        workspaceDataDir: '/data',
        projectPath: '/project',
        toolArgs: { path: 'note.docx', paragraphs: ['Hello'] },
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('.confirmation-card__btn--preview').exists()).toBe(true);
    wrapper.unmount();
  });
});
