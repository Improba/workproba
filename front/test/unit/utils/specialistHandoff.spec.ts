import { describe, expect, it } from 'vitest';
import {
  applyPersonasOpinionFromToolResult,
  appendSpecialistHandoffThinking,
  appendSpecialistHandoffToken,
  createRunningSpecialistHandoff,
  endSpecialistHandoffThinking,
  filterPartsHidingPerspectiveTools,
  initStreamingPersonasOpinion,
  isPerspectiveHandoffTool,
  markPersonasOpinionAsError,
  markRunningSpecialistHandoffAsError,
  markSpecialistHandoffAsPending,
  markSpecialistHandoffAsRunning,
  parseDegradedTools,
  rehydratePerspectiveCards,
  shouldHidePerspectiveToolCall,
  toolResultToSpecialistHandoff,
  upsertSpecialistNestedTool,
} from '@utils/specialistHandoff';
import type { ChatMessage, ChatToolCall } from '#types';

describe('specialistHandoff utils', () => {
  it('identifie les outils de handoff perspective', () => {
    expect(isPerspectiveHandoffTool('ask_personas')).toBe(true);
    expect(isPerspectiveHandoffTool('summon_specialist')).toBe(true);
    expect(isPerspectiveHandoffTool('list_files')).toBe(false);
  });

  it('masque le tool call quand une carte inline est présente', () => {
    const toolCall: ChatToolCall = {
      id: 'tc1',
      name: 'summon_specialist',
      status: 'success',
    };
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      specialistHandoff: createRunningSpecialistHandoff('tc1', {
        specialist_id: 'rh',
        task: 'Analyser le contrat',
        mode: 'regard',
      }),
      createdAt: new Date().toISOString(),
    };
    expect(shouldHidePerspectiveToolCall(message, toolCall)).toBe(true);
  });

  it('ne masque pas summon_specialist pendant une confirmation en cours', () => {
    const toolCall: ChatToolCall = {
      id: 'tc1',
      name: 'summon_specialist',
      status: 'awaiting_confirmation',
    };
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      specialistHandoff: createRunningSpecialistHandoff('tc1', {
        specialist_id: 'rh',
        task: 'Analyser le contrat',
        mode: 'regard',
      }),
      pendingConfirmation: {
        confirmationId: 'cf1',
        toolCallId: 'tc1',
        toolName: 'summon_specialist',
        action: 'create',
        proposedPath: '',
        humanSummary: 'Déléguer',
      },
      createdAt: new Date().toISOString(),
    };
    expect(shouldHidePerspectiveToolCall(message, toolCall)).toBe(false);
  });

  it('ne masque pas summon_specialist pendant une préparation de confirmation', () => {
    const toolCall: ChatToolCall = {
      id: 'tc1',
      name: 'summon_specialist',
      status: 'pending_confirmation',
    };
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      specialistHandoff: createRunningSpecialistHandoff('tc1', {
        specialist_id: 'rh',
        task: 'Analyser le contrat',
        mode: 'regard',
      }),
      preparingConfirmation: {
        toolCallId: 'tc1',
        toolName: 'summon_specialist',
      },
      createdAt: new Date().toISOString(),
    };
    expect(shouldHidePerspectiveToolCall(message, toolCall)).toBe(false);
  });

  it('convertit le résultat summon_specialist en carte terminée', () => {
    const card = toolResultToSpecialistHandoff(
      'tc1',
      { specialist_id: 'rh', task: 'Analyser', mode: 'operative' },
      {
        specialist_id: 'rh',
        specialist_name: 'Gestionnaire',
        mode: 'operative',
        content: 'Synthèse RH',
        degraded_tools: ['managed__x__y'],
      },
    );
    expect(card).toMatchObject({
      specialistName: 'Gestionnaire',
      mode: 'operative',
      content: 'Synthèse RH',
      status: 'done',
      degradedTools: [{ connectorId: 'x', tool: 'y' }],
    });
  });

  it('parse les objets degraded_tools du backend', () => {
    expect(
      parseDegradedTools([
        { connector_id: 'ihora', tool: 'list_absences', reason: 'quota' },
        { connectorId: 'echo', tool: 'ping' },
      ]),
    ).toEqual([
      { connectorId: 'ihora', tool: 'list_absences', reason: 'quota' },
      { connectorId: 'echo', tool: 'ping' },
    ]);
  });

  it('ignore les entrées degraded_tools invalides', () => {
    expect(
      parseDegradedTools([
        { connector_id: 'ihora' },
        '[object Object]',
        { foo: 'bar' },
        'managed__x__y',
      ]),
    ).toEqual([{ connectorId: 'x', tool: 'y' }]);
  });

  it('convertit le résultat summon_specialist avec objets degraded_tools', () => {
    const card = toolResultToSpecialistHandoff(
      'tc1',
      { specialist_id: 'rh', task: 'Analyser', mode: 'operative' },
      {
        specialist_id: 'rh',
        specialist_name: 'Gestionnaire',
        mode: 'operative',
        content: 'Synthèse RH',
        degraded_tools: [
          { connector_id: 'ihora', tool: 'list_absences' },
          { connector_id: 'ihora', tool: 'create_timesheet' },
        ],
      },
    );
    expect(card?.degradedTools).toEqual([
      { connectorId: 'ihora', tool: 'list_absences' },
      { connectorId: 'ihora', tool: 'create_timesheet' },
    ]);
  });

  it('convertit une erreur summon_specialist en carte erreur', () => {
    const card = toolResultToSpecialistHandoff(
      'tc1',
      { specialist_id: 'rh', task: 'Analyser', mode: 'regard' },
      { error: 'boom' },
      true,
    );
    expect(card).toMatchObject({
      specialistId: 'rh',
      status: 'error',
      streaming: false,
    });
  });

  it('convertit un résultat structuré avec error en carte erreur', () => {
    const card = toolResultToSpecialistHandoff(
      'tc1',
      { specialist_id: 'org.gestionnaire', task: 'Analyser', mode: 'regard' },
      {
        specialist_id: 'org.gestionnaire',
        specialist_name: 'org.gestionnaire',
        mode: 'regard',
        content: 'Aucun agent métier synchronisé.',
        error: 'no_business_agents_synced',
      },
    );
    expect(card).toMatchObject({
      specialistId: 'org.gestionnaire',
      status: 'error',
      content: 'Aucun agent métier synchronisé.',
      streaming: false,
    });
  });

  it('renvoie null pour un résultat summon_specialist malformé', () => {
    const card = toolResultToSpecialistHandoff(
      'tc1',
      { specialist_id: 'rh', task: 'Analyser', mode: 'regard' },
      null,
    );
    expect(card).toBeNull();
  });

  it('marque un handoff running en erreur quand le résultat est malformé', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      specialistHandoff: createRunningSpecialistHandoff('tc1', {
        specialist_id: 'rh',
        task: 'Analyser',
      }),
      createdAt: new Date().toISOString(),
    };
    const card = toolResultToSpecialistHandoff('tc1', { specialist_id: 'rh' }, null);
    expect(card).toBeNull();
    markRunningSpecialistHandoffAsError(message);
    expect(message.specialistHandoff).toMatchObject({
      status: 'error',
      streaming: false,
    });
  });

  it('passe un handoff en attente d\'autorisation', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      specialistHandoff: createRunningSpecialistHandoff('tc1', {
        specialist_id: 'rh',
        task: 'Analyser',
      }),
      createdAt: new Date().toISOString(),
    };
    markSpecialistHandoffAsPending(message);
    expect(message.specialistHandoff).toMatchObject({
      status: 'pending',
      streaming: false,
    });
    markSpecialistHandoffAsRunning(message);
    expect(message.specialistHandoff).toMatchObject({
      status: 'running',
      streaming: true,
    });
  });

  it('marque une opinion personas en erreur', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      personasOpinion: initStreamingPersonasOpinion('Budget ?'),
      createdAt: new Date().toISOString(),
    };
    markPersonasOpinionAsError(message);
    expect(message.personasOpinion).toMatchObject({
      question: 'Budget ?',
      streaming: false,
      error: true,
    });
  });

  it('résout le nom et l\'avatar depuis le catalogue personas', () => {
    const card = createRunningSpecialistHandoff(
      'tc1',
      { specialist_id: 'rh', task: 'Analyser', mode: 'regard' },
      (id) =>
        id === 'rh'
          ? { name: 'Nathalie', avatarColor: '#abc', avatarIcon: 'user' }
          : null,
    );
    expect(card).toMatchObject({
      specialistName: 'Nathalie',
      avatarColor: '#abc',
      avatarIcon: 'user',
    });
  });

  it('marque un handoff running en erreur', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      specialistHandoff: createRunningSpecialistHandoff('tc1', {
        specialist_id: 'rh',
        task: 'Analyser',
      }),
      createdAt: new Date().toISOString(),
    };
    markRunningSpecialistHandoffAsError(message);
    expect(message.specialistHandoff).toMatchObject({
      status: 'error',
      streaming: false,
    });
  });

  it('initialise une opinion streaming puis la remplit au résultat', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      personasOpinion: initStreamingPersonasOpinion('Salaire ?'),
      createdAt: new Date().toISOString(),
    };
    applyPersonasOpinionFromToolResult(
      message,
      { question: 'Salaire ?' },
      {
        opinions: [
          {
            persona_id: 'rh',
            persona_name: 'Nathalie',
            role: 'RH',
            content: 'À revoir',
          },
        ],
      },
    );
    expect(message.personasOpinion?.streaming).toBe(false);
    expect(message.personasOpinion?.opinions[0]?.personaName).toBe('Nathalie');
  });

  it('marque une opinion en erreur quand le résultat est malformé', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      personasOpinion: initStreamingPersonasOpinion('Budget ?'),
      createdAt: new Date().toISOString(),
    };
    applyPersonasOpinionFromToolResult(message, { question: 'Budget ?' }, null);
    expect(message.personasOpinion).toMatchObject({
      question: 'Budget ?',
      streaming: false,
      error: true,
    });
  });

  it('rehydrate une carte handoff terminée depuis les toolCalls', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      toolCalls: [
        {
          id: 'tc1',
          name: 'summon_specialist',
          status: 'success',
          args: { specialist_id: 'rh', task: 'Analyser', mode: 'regard' },
          result: {
            specialist_id: 'rh',
            specialist_name: 'Gestionnaire',
            content: 'Synthèse',
          },
        },
      ],
      createdAt: new Date().toISOString(),
    };
    rehydratePerspectiveCards(message);
    expect(message.specialistHandoff).toMatchObject({
      specialistName: 'Gestionnaire',
      content: 'Synthèse',
      status: 'done',
    });
  });

  it('rehydrate une opinion personas depuis les toolCalls', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      toolCalls: [
        {
          id: 'tc1',
          name: 'ask_personas',
          status: 'success',
          args: { question: 'Budget ?' },
          result: {
            opinions: [
              {
                persona_id: 'rh',
                persona_name: 'Nathalie',
                role: 'RH',
                content: 'OK',
              },
            ],
          },
        },
      ],
      createdAt: new Date().toISOString(),
    };
    rehydratePerspectiveCards(message);
    expect(message.personasOpinion?.opinions[0]?.personaName).toBe('Nathalie');
    expect(message.personasOpinion?.streaming).toBe(false);
  });

  it('rehydrate un handoff running depuis les toolCalls', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      toolCalls: [
        {
          id: 'tc1',
          name: 'summon_specialist',
          status: 'running',
          args: { specialist_id: 'rh', task: 'Analyser', mode: 'regard' },
        },
      ],
      createdAt: new Date().toISOString(),
    };
    rehydratePerspectiveCards(message);
    expect(message.specialistHandoff).toMatchObject({
      specialistId: 'rh',
      status: 'running',
      streaming: true,
    });
  });

  it('filtre les parts tool_call masquées', () => {
    const message: ChatMessage = {
      id: 'm1',
      role: 'assistant',
      content: '',
      toolCalls: [{ id: 'tc1', name: 'ask_personas', status: 'running' }],
      personasOpinion: initStreamingPersonasOpinion('Budget ?'),
      createdAt: new Date().toISOString(),
    };
    const parts = filterPartsHidingPerspectiveTools(
      [
        { type: 'text', id: 'p1', content: 'Ok' },
        { type: 'tool_call', id: 'p2', toolCallId: 'tc1' },
      ],
      message,
    );
    expect(parts).toHaveLength(1);
    expect(parts[0].type).toBe('text');
  });

  it('appendSpecialistHandoffToken et thinking préservent id handoff', () => {
    const card = createRunningSpecialistHandoff('tc1', {
      specialist_id: 'rh',
      task: 'Analyser',
      mode: 'regard',
    });
    const withToken = appendSpecialistHandoffToken(card, 'Hello');
    const withThinking = appendSpecialistHandoffThinking(withToken, 'Réflexion');
    const withDone = endSpecialistHandoffThinking(withThinking);
    const withTool = upsertSpecialistNestedTool(withDone, {
      id: 'nested-1',
      name: 'managed__ihora__list_absences',
      status: 'running',
    });

    expect(withTool.id).toBe(card.id);
    expect(withTool.content).toBe('Hello');
    expect(withTool.thinking).toBe('Réflexion');
    expect(withTool.thinkingDone).toBe(true);
    expect(withTool.nestedTools).toEqual([
      expect.objectContaining({ id: 'nested-1', status: 'running' }),
    ]);
  });
});
