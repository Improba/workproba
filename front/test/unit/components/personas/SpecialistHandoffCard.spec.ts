import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import SpecialistHandoffCard from '@components/personas/SpecialistHandoffCard.vue';
import PersonasOpinionCard from '@components/personas/PersonasOpinionCard.vue';
import type { PersonasOpinionCard as PersonasOpinionCardType, SpecialistHandoffCard as SpecialistHandoffCardType } from '#types';

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (key === 'personas.handoff.takeoverDone') {
        return `${params?.name} a rendu son avis`;
      }
      if (key === 'personas.handoff.takeoverDoneOperative') {
        return `${params?.name} a traité la demande`;
      }
      if (key === 'personas.handoff.analysing') {
        return `${params?.name} analyse…`;
      }
      if (key === 'personas.handoff.detailWhileRunning') {
        return `Activité de ${params?.name}`;
      }
      if (key === 'personas.handoff.detailActivity') {
        return `Activité de ${params?.name}`;
      }
      if (key === 'personas.handoff.degradedToolsNamed') {
        return `Certains outils étaient indisponibles (${params?.names}).`;
      }
      if (key === 'personas.handoff.discuss') {
        return `Continuer avec ${params?.name}`;
      }
      if (key === 'personas.handoff.talk') {
        return `Parler à ${params?.name}`;
      }
      const labels: Record<string, string> = {
        'personas.handoff.cardLabel': 'Retour de {name}',
        'personas.handoff.retry': 'Réessayer',
        'personas.handoff.modeRegard': 'Avis',
        'personas.handoff.modeOperative': 'Action',
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
    specialistName: 'Gestionnaire',
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
    degradedTools: [{ connectorId: 'x', tool: 'y' }],
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
    expect(wrapper.text()).toContain('Gestionnaire');
    expect(wrapper.text()).toContain('Avis');
    expect(wrapper.find('.specialist-handoff-card__badge').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Agent métier · Action');
    expect(wrapper.text()).not.toContain('prend le relais');
    expect(wrapper.text()).toContain('Analyser le contrat');
    expect(wrapper.text()).toContain('Gestionnaire analyse…');
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(true);
    expect(wrapper.find('[role="status"].wp-sr-only').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('En cours');
  });

  it('affiche la réponse done sans ouvrir le détail', () => {
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
    expect(wrapper.text()).toContain('Activité de Gestionnaire');
    expect(wrapper.text()).toContain('Voir le détail');
    expect(wrapper.find('.stub-text').text()).toContain('Saisie enregistrée avec succès.');
    expect(wrapper.find('[data-testid="thinking-card"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('Je vérifie le projet Test.');
  });

  it('révèle réflexion et outils après Voir le détail', async () => {
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
    expect(wrapper.findAll('.stub-text')).toHaveLength(1);
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

  it('affiche l\'état pending sans spinner ni doublon d\'autorisation', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: { ...pendingCard(), id: 'h-pending-empty' } },
      global: { stubs: globalStubs },
    });
    const pendingMatches = wrapper.text().match(/En attente de votre autorisation…/g);
    expect(pendingMatches).toHaveLength(2);
    expect(wrapper.text()).toContain('Gestionnaire');
    expect(wrapper.text()).not.toContain('Autorisation demandée pour');
    expect(wrapper.text()).not.toContain('prend le relais');
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('En cours');
  });

  it('affiche le contenu, les outils dégradés condensés et le CTA Continuer à la fin', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: { ...doneCard(), id: 'h-done-cta' } },
      global: { stubs: globalStubs },
    });
    expect(wrapper.find('.specialist-handoff-card__badge').exists()).toBe(false);
    expect(wrapper.text()).toContain('Avis');
    expect(wrapper.text()).toContain('Gestionnaire');
    expect(wrapper.text()).not.toContain('Agent métier');
    expect(wrapper.text()).toContain('Certains outils étaient indisponibles (x).');
    expect(wrapper.text()).not.toContain("J'ai effectué une action");
    expect(wrapper.find('.stub-text').text()).toContain('Voici la synthèse.');
    expect(wrapper.text()).toContain('Continuer avec Gestionnaire');
    await wrapper.get('.specialist-handoff-card__action--discuss').trigger('click');
    expect(wrapper.emitted('discuss')).toHaveLength(1);
  });

  it('affiche l\'état erreur avec Réessayer et Continuer', async () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: errorCard() },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Gestionnaire');
    expect(wrapper.text()).toContain('Échec');
    expect(wrapper.text()).toContain('La délégation à l\'agent métier a échoué.');
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    expect(wrapper.find('.specialist-handoff-preview__spinner').exists()).toBe(false);
    expect(wrapper.text()).not.toContain('En cours');
    expect(wrapper.text()).toContain('Parler à Gestionnaire');
    await wrapper.get('.specialist-handoff-card__action--retry').trigger('click');
    expect(wrapper.emitted('retry')).toHaveLength(1);
    await wrapper.get('.specialist-handoff-card__action--discuss').trigger('click');
    expect(wrapper.emitted('discuss')).toHaveLength(1);
  });

  it('affiche le contenu d\'erreur structuré avec le mode Action', () => {
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
    expect(wrapper.text()).toContain('Action');
    expect(wrapper.text()).toContain('Échec');
    expect(wrapper.text()).not.toContain('Agent métier · Action');
    expect(wrapper.find('.specialist-handoff-card__badge').exists()).toBe(false);
    expect(wrapper.find('[role="alert"]').text()).toContain(
      'Aucun agent métier synchronisé dans cet espace.',
    );
    expect(wrapper.text()).not.toContain('La délégation à l\'agent métier a échoué.');
  });

  it('montre les outils nested pendant l\'analyse sans ouvrir le détail', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: {
        card: {
          ...runningCard(),
          id: 'h-live-tools',
          nestedTools: [
            {
              id: 'nt1',
              name: 'read_document',
              humanSummary: 'Lecture du contrat',
              status: 'running',
            },
          ],
        },
      },
      global: { stubs: globalStubs },
    });
    expect(wrapper.text()).toContain('Lecture du contrat');
    expect(wrapper.find('.specialist-handoff-card__nested-tools--live').exists()).toBe(true);
    expect(wrapper.find('.specialist-handoff-preview').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('Voir le détail');
    expect(wrapper.find('[data-testid="thinking-card"]').exists()).toBe(false);
  });

  it('n’affiche pas Réessayer quand la délégation n’est plus le dernier message', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: errorCard(), hideRetry: true },
      global: { stubs: globalStubs },
    });
    expect(wrapper.find('.specialist-handoff-card__action--retry').exists()).toBe(false);
    expect(wrapper.text()).toContain('Parler à Gestionnaire');
  });

  it('désactive Réessayer pendant un échange en cours', () => {
    const wrapper = mount(SpecialistHandoffCard, {
      props: { card: errorCard(), retryDisabled: true },
      global: { stubs: globalStubs },
    });
    expect(
      wrapper.get('.specialist-handoff-card__action--retry').attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper.get('.specialist-handoff-card__action--retry').attributes('title'),
    ).toBe('personas.handoff.retryBusy');
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
