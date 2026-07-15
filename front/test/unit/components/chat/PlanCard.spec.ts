import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import PlanCard from '@components/chat/PlanCard.vue';
import type { ChatProposedPlan } from '#types';

function basePlan(overrides: Partial<ChatProposedPlan> = {}): ChatProposedPlan {
  return {
    planId: 'plan_1',
    rationale: 'Tâche multi-étapes',
    steps: [
      { tool: 'write_docx', summary: 'Créer le contrat', target: 'contrat.docx' },
    ],
    status: 'pending',
    ...overrides,
  };
}

describe('PlanCard', () => {
  it('affiche le titre de replan quand isReplan est vrai', () => {
    const wrapper = mount(PlanCard, {
      props: { plan: basePlan({ isReplan: true }) },
      global: { stubs: { Lucide: true } },
    });

    expect(wrapper.find('.plan-card__title').text()).toBe('Plan mis à jour');
    wrapper.unmount();
  });

  it('affiche le titre initial sans replan', () => {
    const wrapper = mount(PlanCard, {
      props: { plan: basePlan({ isReplan: false }) },
      global: { stubs: { Lucide: true } },
    });

    expect(wrapper.find('.plan-card__title').text()).toBe('Plan proposé');
    wrapper.unmount();
  });
});
