import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it } from 'vitest';
import ActivityGroup from '@components/chat/ActivityGroup.vue';
import { clearExpansionState } from '@composables/useToolCallExpansion';
import type { ActivityGroupData } from '@utils/activityGroup';

const baseGroup: ActivityGroupData = {
  id: 'think-1',
  parts: [
    {
      type: 'thinking',
      id: 'think-1',
      thinkingId: 'think-0',
      content: 'Analyse',
      done: true,
    },
    { type: 'tool_call', id: 'tc-part-1', toolCallId: 'tc-1' },
    { type: 'tool_call', id: 'tc-part-2', toolCallId: 'tc-2' },
  ],
  toolCallIds: ['tc-1', 'tc-2'],
};

const toolCalls = [
  { id: 'tc-1', name: 'managed__ihora__list_absences', status: 'success' as const },
  { id: 'tc-2', name: 'managed__ihora__get_timesheet', status: 'error' as const },
];

describe('ActivityGroup', () => {
  beforeEach(() => {
    clearExpansionState();
  });

  it('affiche le résumé replié par défaut', () => {
    const wrapper = mount(ActivityGroup, {
      props: { group: baseGroup, toolCalls },
      global: {
        stubs: {
          Lucide: true,
          ThinkingCard: true,
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    const toggle = wrapper.find('.activity-group__toggle');
    expect(toggle.exists()).toBe(true);
    expect(toggle.attributes('aria-expanded')).toBe('false');
    expect(toggle.text()).toContain('Utilisé 2 outils');
    expect(toggle.text()).toContain('1 erreur');
    expect(toggle.text()).toContain('ihora');
    expect(wrapper.find('.activity-group__panel').exists()).toBe(false);
    wrapper.unmount();
  });

  it('déplie le panneau au clic', async () => {
    const wrapper = mount(ActivityGroup, {
      props: { group: baseGroup, toolCalls },
      global: {
        stubs: {
          Lucide: true,
          ThinkingCard: { template: '<div class="thinking-card-stub" />' },
          ToolCallCard: { template: '<div class="tool-call-card-stub" />' },
          ConfirmationCard: true,
        },
      },
    });

    await wrapper.find('.activity-group__toggle').trigger('click');
    expect(wrapper.find('.activity-group__toggle').attributes('aria-expanded')).toBe(
      'true',
    );
    expect(wrapper.find('.activity-group__panel').exists()).toBe(true);
    expect(wrapper.findAll('.tool-call-card-stub')).toHaveLength(2);
    wrapper.unmount();
  });

  it('force l ouverture quand une confirmation est en attente', () => {
    const wrapper = mount(ActivityGroup, {
      props: {
        group: baseGroup,
        toolCalls,
        pendingConfirmation: {
          confirmationId: 'cf-1',
          toolCallId: 'tc-2',
          toolName: 'write_docx',
          action: 'create',
          proposedPath: 'out.docx',
          humanSummary: 'Créer',
        },
      },
      global: {
        stubs: {
          Lucide: true,
          ThinkingCard: true,
          ToolCallCard: true,
          ConfirmationCard: { template: '<div class="confirmation-card-stub" />' },
        },
      },
    });

    expect(wrapper.find('.activity-group__toggle').attributes('aria-expanded')).toBe(
      'true',
    );
    expect(wrapper.find('.activity-group__panel').exists()).toBe(true);
    expect(wrapper.find('.confirmation-card-stub').exists()).toBe(true);
    wrapper.unmount();
  });

  it('affiche le résumé raisonnement pour un groupe thinking-only en streaming', () => {
    const thinkingOnlyGroup: ActivityGroupData = {
      id: 'think-only',
      parts: [
        {
          type: 'thinking',
          id: 'think-only',
          thinkingId: 'think-0',
          content: 'Je réfléchis',
          done: false,
        },
      ],
      toolCallIds: [],
    };

    const wrapper = mount(ActivityGroup, {
      props: { group: thinkingOnlyGroup, streaming: true },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
          ThinkingCard: true,
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    const toggle = wrapper.find('.activity-group__toggle');
    expect(toggle.text()).toContain('Le modèle réfléchit');
    expect(toggle.text()).not.toContain('Utilisé 0 outil');
    expect(wrapper.find('.activity-group__spinner').exists()).toBe(true);
    wrapper.unmount();
  });

  it('affiche Raisonnement pour un groupe thinking-only terminé', () => {
    const thinkingOnlyGroup: ActivityGroupData = {
      id: 'think-done',
      parts: [
        {
          type: 'thinking',
          id: 'think-done',
          thinkingId: 'think-0',
          content: 'Analyse terminée',
          done: true,
        },
      ],
      toolCallIds: [],
    };

    const wrapper = mount(ActivityGroup, {
      props: { group: thinkingOnlyGroup, streaming: false },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
          ThinkingCard: true,
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    expect(wrapper.find('.activity-group__toggle').text()).toContain('Raisonnement');
    wrapper.unmount();
  });

  it('passe embedded à ThinkingCard quand déplié', async () => {
    const thinkingOnlyGroup: ActivityGroupData = {
      id: 'think-embed',
      parts: [
        {
          type: 'thinking',
          id: 'think-embed',
          thinkingId: 'think-0',
          content: 'Contenu',
          done: true,
        },
      ],
      toolCallIds: [],
    };

    const wrapper = mount(ActivityGroup, {
      props: { group: thinkingOnlyGroup },
      global: {
        stubs: {
          Lucide: true,
          'q-icon': true,
          ThinkingCard: {
            name: 'ThinkingCard',
            props: ['thinking', 'streaming', 'embedded'],
            template: '<div class="thinking-card-stub" />',
          },
          ToolCallCard: true,
          ConfirmationCard: true,
        },
      },
    });

    await wrapper.find('.activity-group__toggle').trigger('click');

    const thinkingCard = wrapper.findComponent({ name: 'ThinkingCard' });
    expect(thinkingCard.exists()).toBe(true);
    expect(thinkingCard.props('embedded')).toBe(true);
    wrapper.unmount();
  });
});
