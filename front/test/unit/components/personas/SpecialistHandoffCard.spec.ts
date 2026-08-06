import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import SpecialistHandoffCard from '@components/personas/SpecialistHandoffCard.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import type { PersonasOpinionCard as PersonasOpinionCardType, SpecialistHandoffCard as SpecialistHandoffCardType } from '#types';

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (key === 'personas.handoff.takeoverRunning') {
        return `${params?.name} prend le relais (${params?.mode})…`;
      }
      if (key === 'personas.handoff.takeoverDone') {
        return `${params?.name} a pris le relais (${params?.mode})`;
      }
      if (key === 'personas.handoff.takeoverError') {
        return `La délégation à ${params?.name} (${params?.mode}) a échoué`;
      }
      if (key === 'personas.handoff.analysing') {
        return `${params?.name} analyse…`;
      }
      const labels: Record<string, string> = {
        'personas.handoff.cardLabel': 'Retour de {name}',
        'personas.handoff.badge': 'Agent métier',
        'personas.handoff.modeRegard': 'Regard',
        'personas.handoff.modeOperative': 'Opératoire',
        'personas.handoff.discuss': 'Discuter',
        'personas.handoff.statusFailed': 'Échec',
        'personas.handoff.error': 'La délégation à l\'agent métier a échoué.',
        'personas.handoff.pendingAuthorization': 'En attente de votre autorisation…',
        'personas.handoff.degradedTools': 'Certains outils étaient indisponibles pour cet agent.',
        'personas.opinion.error': 'La consultation des regards a échoué.',
        'personas.opinion.header': 'Avis sur {topic}',
        'common.inProgress': 'En cours',
      };
      return labels[key] ?? key;
    },
  }),
}));

function runningCard(): SpecialistHandoffCardType {
  return {
    id: 'h1',
    toolCallId: 'tc1',
    specialistId: 'rh',
    specialistName: 'Agent RH',
    mode: 'regard',
    task: 'Analyser le contrat',
    content: '',
    status: 'running',
    streaming: true,
  };
}

function pendingCard(): SpecialistHandoffCardType {
  return {
    ...runningCard(),
    status: 'pending',
    streaming: false,
  };
}

function doneCard(): SpecialistHandoffCardType {
  return {
    ...runningCard(),
    content: 'Voici la synthèse.',
    degradedTools: ['managed__x__y'],
    status: 'done',
    streaming: false,
  };
}

function errorCard(): SpecialistHandoffCardType {
  return {
    ...runningCard(),
    status: 'error',
    streaming: false,
  };
}

const globalStubs = {
  PersonaAvatar: true,
  MessageTextPart: true,
  Lucide: true,
  MemoryCitationsBar: true,
};

describe('SpecialistHandoffCard', () => {
  it('affiche la preview running avec spinner', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: runningCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Agent RH prend le relais (Regard)…');
    expect(wrapper.text()).toContain('Analyser le contrat');
    expect(wrapper.text()).toContain('Agent RH analyse…');
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(true);
    expect(wrapper.find('[role="status"].wp-sr-only').exists()).toBe(true);
  });

  it('affiche l\'état pending sans spinner', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: pendingCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('En attente de votre autorisation…');
    expect(wrapper.text()).not.toContain('prend le relais');
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('En cours');
  });

  it('affiche le contenu, les outils dégradés et le CTA Discuter à la fin', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: doneCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Agent métier');
    expect(wrapper.text()).toContain('x · y');
    expect(wrapper.text()).not.toContain('managed__x__y');
    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('discuss')).toHaveLength(1);
  });

  it('affiche l\'état erreur avec CTA Discuter', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: errorCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('La délégation à Agent RH (Regard) a échoué');
    expect(wrapper.text()).toContain('Échec');
    expect(wrapper.text()).toContain('La délégation à l\'agent métier a échoué.');
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('En cours');
    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('discuss')).toHaveLength(1);
  });
});

describe('PersonasOpinionCard', () => {
  it('affiche un message d\'erreur accessible sans CTAs', () => {
    const card: PersonasOpinionCardType = {
      id: 'o1',
      question: 'Budget ?',
      opinions: [],
      streaming: false,
      error: true,
    };
    const wrapper = mount(PersonasOpinionCard, {
      props: { card },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('La consultation des regards a échoué.');
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    expect(wrapper.find('.personas-opinion-card__actions').exists()).toBe(false);
  });
});
