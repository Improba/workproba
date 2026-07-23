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
  it('affiche le summary enrichi avec utilisateur résolu', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          toolName: 'managed__ihora__update_project_member',
          effect: 'external_send',
          headline: 'Action externe : ihora',
          humanSummary:
            'Je vais mettre à jour le membre Sylvain Meylan (sylvain.meylan@improba.ch, userId 7) sur ihora',
          proposedPath: '',
        }),
        toolArgs: {
          connector_id: 'ihora',
          action: 'update_project_member',
          projectId: 42,
          email: 'sylvain.meylan@improba.ch',
          role: 'manager',
        },
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('.confirmation-card__headline').text()).toContain('Sylvain Meylan');
    expect(wrapper.find('.confirmation-card__headline').text()).toContain('userId 7');
    const args = wrapper.find('[data-testid="confirmation-args"]');
    expect(args.text()).not.toContain('sylvain.meylan@improba.ch');
    expect(args.text()).toContain('projectId');
    expect(args.text()).toContain('42');
    wrapper.unmount();
  });

  it('masque userId et email bruts quand le summary affiche déjà la résolution', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          toolName: 'managed__ihora__update_project_member',
          effect: 'external_send',
          headline: 'Action externe : ihora',
          humanSummary:
            'Je vais mettre à jour le membre Sylvain Meylan (sylvain.meylan@improba.ch, userId 7) sur ihora',
          proposedPath: '',
        }),
        toolArgs: {
          connector_id: 'ihora',
          action: 'update_project_member',
          projectId: 42,
          userId: 1,
          email: 'sylvain.meylan@improba.ch',
          role: 'manager',
        },
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    const args = wrapper.find('[data-testid="confirmation-args"]');
    expect(args.text()).toContain('projectId');
    expect(args.text()).toContain('role');
    expect(args.text()).not.toMatch(/\buserId\b/);
    expect(args.text()).not.toContain('sylvain.meylan@improba.ch');
    wrapper.unmount();
  });

  it('priorise humanSummary pour external_send avec headline vague', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          toolName: 'invoke_managed_connector',
          effect: 'external_send',
          headline: 'Action externe : ihora',
          humanSummary: 'Je vais appeler update project member sur ihora',
          proposedPath: '',
          protectionLabels: ['Confirmation requise'],
        }),
        toolArgs: {
          connector_id: 'ihora',
          action: 'update_project_member',
          projectId: 42,
          userId: 'sylvain.meylan',
          role: 'manager',
        },
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('.confirmation-card__headline').text()).toContain('update project member');
    expect(wrapper.find('.confirmation-card__secondary').exists()).toBe(false);
    const args = wrapper.find('[data-testid="confirmation-args"]');
    expect(args.exists()).toBe(true);
    expect(args.text()).toContain('projectId');
    expect(args.text()).toContain('42');
    expect(args.text()).toContain('userId');
    expect(args.text()).toContain('sylvain.meylan');
    expect(args.text()).not.toContain('connector_id');
    expect(wrapper.findAll('[data-testid="confirmation-protections"] li')).toHaveLength(1);
    wrapper.unmount();
  });

  it('affiche une cible secondaire quand headline apporte une cible absente du summary', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          toolName: 'invoke_managed_connector',
          effect: 'external_send',
          headline: 'Action externe : salesforce',
          humanSummary: 'Je vais appeler update project member',
          proposedPath: '',
        }),
      },
      global: {
        stubs: {
          PreviewChangeDialog: true,
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('.confirmation-card__headline').text()).toContain('update project member');
    expect(wrapper.find('.confirmation-card__secondary').text()).toBe('Cible : salesforce');
    wrapper.unmount();
  });

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

  it('affiche le bouton preview pour write_pptx et passe les props au dialog', () => {
    const wrapper = mount(ConfirmationCard, {
      props: {
        confirmation: baseConfirmation({
          toolName: 'write_pptx',
          proposedPath: 'pitch.pptx',
          headline: 'Je vais Créer : pitch.pptx',
        }),
        workspaceDataDir: '/data',
        projectPath: '/project',
        toolArgs: {
          path: 'pitch.pptx',
          slides: [{ layout: 'title', title: 'Hello' }],
        },
      },
      global: {
        stubs: {
          PreviewChangeDialog: {
            name: 'PreviewChangeDialog',
            props: [
              'open',
              'workspaceDataDir',
              'projectPath',
              'filePath',
              'toolName',
              'toolArgs',
            ],
            template: '<div data-testid="preview-stub" />',
          },
          Lucide: true,
        },
      },
    });

    expect(wrapper.find('.confirmation-card__btn--preview').exists()).toBe(true);
    const dialog = wrapper.findComponent({ name: 'PreviewChangeDialog' });
    expect(dialog.exists()).toBe(true);
    expect(dialog.props('toolName')).toBe('write_pptx');
    expect(dialog.props('filePath')).toBe('pitch.pptx');
    expect(dialog.props('toolArgs')).toMatchObject({ path: 'pitch.pptx' });
    wrapper.unmount();
  });
});
