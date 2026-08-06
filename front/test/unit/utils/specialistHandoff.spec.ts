import { describe, expect, it } from 'vitest';
import {
  applyPersonasOpinionFromToolResult,
  createRunningSpecialistHandoff,
  filterPartsHidingPerspectiveTools,
  initStreamingPersonasOpinion,
  isPerspectiveHandoffTool,
  markPersonasOpinionAsError,
  markRunningSpecialistHandoffAsError,
  markSpecialistHandoffAsPending,
  markSpecialistHandoffAsRunning,
  shouldHidePerspectiveToolCall,
  toolResultToSpecialistHandoff,
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

  it('convertit le résultat summon_specialist en carte terminée', () => {
    const card = toolResultToSpecialistHandoff(
      'tc1',
      { specialist_id: 'rh', task: 'Analyser', mode: 'operative' },
      {
        specialist_id: 'rh',
        specialist_name: 'Agent RH',
        mode: 'operative',
        content: 'Synthèse RH',
        degraded_tools: ['managed__x__y'],
      },
    );
    expect(card).toMatchObject({
      specialistName: 'Agent RH',
      mode: 'operative',
      content: 'Synthèse RH',
      status: 'done',
      degradedTools: ['managed__x__y'],
    });
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
});
