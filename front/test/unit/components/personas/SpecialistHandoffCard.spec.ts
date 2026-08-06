import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import SpecialistHandoffCard from '@components/personas/SpecialistHandoffCard.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import type { PersonasOpinionCard as PersonasOpinionCardType, SpecialistHandoffCard as SpecialistHandoffCardType } from '#types';

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (key === 'personas.handoff.badgeWithMode') {
        return `${params?.badge} · ${params?.mode}`;
      }
      if (key === 'personas.handoff.takeoverRunning') {
        return `${params?.name} prend le relais…`;
      }
      if (key === 'personas.handoff.takeoverDone') {
        return `${params?.name} a pris le relais`;
      }
      if (key === 'personas.handoff.takeoverError') {
        return `La délégation à ${params?.name} a échoué`;
      }
      if (key === 'personas.handoff.analysing') {
        return `${params?.name} analyse…`;
      }
      if (key === 'personas.handoff.detailWhileRunning') {
        return `Activité de ${params?.name}`;
      }
      if (key === 'personas.handoff.detailDone') {
        return `Réponse de ${params?.name}`;
      }
      const labels: Record<string, string> = {
        'personas.handoff.cardLabel': 'Retour de {name}',
        'personas.handoff.badge': 'Agent métier',
        'personas.handoff.modeRegard': 'Regard',
        'personas.handoff.modeOperative': 'Action',
        'personas.handoff.discuss': 'Discuter',
        'personas.handoff.statusFailed': 'Échec',
        'personas.handoff.error': 'La délégation à l\'agent métier a échoué.',
        'personas.handoff.pendingAuthorization': 'En attente de votre autorisation…',
        'personas.handoff.nestedTools': 'Outils de l\'agent',
        'personas.handoff.detailRegion': 'Détail de la délégation',
        'personas.handoff.degradedTools': 'Certains outils étaient indisponibles pour cet agent.',
        'personas.opinion.error': 'La consultation des regards a échoué.',
        'personas.opinion.header': 'Avis sur {topic}',
        'common.inProgress': 'En cours',
        'common.show': 'Voir le détail',
        'common.hide': 'Masquer',
        'chat.thinking': 'Réflexion…',
        'chat.reasoning': 'Raisonnement',
        'chat.thinkingPlaceholder': 'Détails du raisonnement…',
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
  MessageTextPart: {
    props: ['content', 'streaming'],
    template: '<div class="stub-text">{{ content }}</div>',
  },
  ThinkingCard: {
    props: ['thinking', 'streaming', 'embedded'],
    template:
      '<div class="stub-thinking" data-testid="thinking-card">{{ thinking?.content }}</div>',
  },
  Lucide: true,
  MemoryCitationsBar: true,
  SpecialistHandoffPreview: {
    props: ['name', 'label'],
    template:
      '<div class="specialist-handoff-preview"><span>{{ label }}</span><span class="specialist-handoff-preview__spinner" /></div>',
  },
};

describe('SpecialistHandoffCard', () => {
  it('affiche la preview running avec spinner', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: runningCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Agent RH prend le relais…');
    expect(wrapper.text()).toContain('Agent métier · Regard');
    expect(wrapper.text()).toContain('Analyser le contrat');
    expect(wrapper.text()).toContain('Agent RH analyse…');
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(true);
    expect(wrapper.find('[role="status"].wp-sr-only').exists()).toBe(true);
  });

  it('ne montre pas la réponse dans l\'encart tant que le détail est fermé', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: {
        card: {
          ...doneCard(),
          id: 'h-collapsed',
          thinking: 'Je vérifie le projet Test.',
          thinkingDone: true,
          nestedTools: [
            {
              id: 'nt1',
              name: 'create_timesheet',
              humanSummary: 'Création de la saisie',
              status: 'success',
            },
          ],
          content: 'Saisie enregistrée avec succès.',
        },
      },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Réponse de Agent RH');
    expect(wrapper.text()).toContain('Voir le détail');
    expect(wrapper.find('.stub-text').exists()).toBe(false);
    expect(wrapper.find('[data-testid="thinking-card"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Saisie enregistrée avec succès.');
    expect(wrapper.text()).not.toContain('Je vérifie le projet Test.');
  });

  it('révèle réflexion, outils et réponse après Voir le détail', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: {
        card: {
          ...doneCard(),
          id: 'h-expand',
          thinking: 'Je vérifie le projet Test.',
          thinkingDone: true,
          nestedTools: [
            {
              id: 'nt1',
              name: 'create_timesheet',
              humanSummary: 'Création de la saisie',
              status: 'success',
            },
          ],
          content: 'Saisie enregistrée avec succès.',
        },
      },
      global: { stubs: globalStubs },
    });
    await wrapper.get('.specialist-handoff-card__detail-toggle').trigger('click');
    expect(wrapper.find('[data-testid="thinking-card"]').text()).toContain(
      'Je vérifie le projet Test.',
    );
    expect(wrapper.text()).toContain('Création de la saisie');
    expect(wrapper.find('.stub-text').text()).toContain('Saisie enregistrée avec succès.');
    expect(wrapper.text()).toContain('Masquer');
  });

  it('conserve le détail repliable pendant pending (HAG)', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: {
        card: {
          ...pendingCard(),
          id: 'h-pending-detail',
          thinking: 'Je vais créer la saisie.',
          thinkingDone: true,
          content: 'Prêt à écrire dans Ihora.',
          nestedTools: [
            {
              id: 'nt1',
              name: 'create_timesheet',
              humanSummary: 'Création de la saisie',
              status: 'running',
            },
          ],
        },
      },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('En attente de votre autorisation…');
    expect(wrapper.text()).toContain('Voir le détail');
    expect(wrapper.find('.stub-text').exists()).toBe(false);
    await wrapper.get('.specialist-handoff-card__detail-toggle').trigger('click');
    expect(wrapper.text()).toContain('Prêt à écrire dans Ihora.');
    expect(wrapper.text()).toContain('Création de la saisie');
  });

  it('affiche l\'état pending sans spinner', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: { ...pendingCard(), id: 'h-pending-empty' } },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('En attente de votre autorisation…');
    expect(wrapper.text()).not.toContain('prend le relais');
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('En cours');
  });

  it('affiche le contenu, les outils dégradés et le CTA Discuter à la fin', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: { ...doneCard(), id: 'h-done-cta' } },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Agent métier · Regard');
    expect(wrapper.find('.specialist-handoff-card__badge').exists()).toBe(true);
    expect(wrapper.find('.specialist-handoff-card__mode').exists()).toBe(false);
    expect(wrapper.text()).toContain('x · y');
    expect(wrapper.text()).not.toContain('managed__x__y');
    // Contenu derrière détail
    expect(wrapper.find('.stub-text').exists()).toBe(false);
    await wrapper.get('.specialist-handoff-card__detail-toggle').trigger('click');
    expect(wrapper.find('.stub-text').text()).toContain('Voici la synthèse.');
    await wrapper.get('.specialist-handoff-card__action').trigger('click');
    expect(wrapper.emitted('discuss')).toHaveLength(1);
  });

  it('affiche l\'état erreur avec CTA Discuter', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: errorCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('La délégation à Agent RH a échoué');
    expect(wrapper.text()).toContain('Échec');
    expect(wrapper.text()).toContain('La délégation à l\'agent métier a échoué.');
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('En cours');
    await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('discuss')).toHaveLength(1);
  });

  it('affiche le contenu d\'erreur structuré et le badge Action', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: {
        card: {
          ...errorCard(),
          mode: 'operative',
          content: 'Aucun agent métier synchronisé dans cet espace.',
        },
      },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Agent métier · Action');
    expect(wrapper.find('[role="alert"]').text()).toContain(
      'Aucun agent métier synchronisé dans cet espace.',
    );
    expect(wrapper.text()).not.toContain('La délégation à l\'agent métier a échoué.');
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
