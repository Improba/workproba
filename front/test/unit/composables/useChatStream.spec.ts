import { defineComponent, ref, type Ref } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks des dépendances réseau/config avant l'import du composable.
vi.mock('@services/aiSidecar', () => ({
  getAiSidecarUrl: () => 'http://127.0.0.1:8765',
  getDesktopSecret: () => 'desktop-dev-secret',
  buildAgentTurnPayload: vi.fn(() => ({ message: 'fake' })),
}));
vi.mock('@composables/useAppSettings', () => ({
  buildActiveLlmConfigs: () => ({ chat: null, embedding: null }),
}));

import { useChatStream, mapPythonSseEvent, applyStreamEvent, mergeLlmConfigsWithSessionReasoning, type UseChatStreamReturn } from '@composables/useChatStream';
import type { ChatMessage } from '#types';

/** Construit une Response SSE dont le body émet `events` puis ferme le flux. */
function sseResponse(
  events: Array<{ event: string; data: unknown }>,
  init: { ok?: boolean; status?: number } = {},
): Response {
  const text = events
    .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
    .join('');
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    body,
    headers: new Headers(),
  } as unknown as Response;
}

interface Harness {
  api: UseChatStreamReturn;
  projectPath: Ref<string | null>;
  unmount: () => void;
}

function mountStream(projectPath: string | null = '/proj'): Harness {
  const projectPathRef = ref<string | null>(projectPath);
  let api!: UseChatStreamReturn;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useChatStream({
          sessionId: ref('sess-1'),
          projectPath: projectPathRef,
        });
        return {};
      },
      template: '<div />',
    }),
  );
  return { api, projectPath: projectPathRef, unmount: () => wrapper.unmount() };
}

function lastAssistant(messages: ChatMessage[]): ChatMessage | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant') return messages[i];
  }
  return undefined;
}

describe('useChatStream — feedbacks', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('accumule les tokens puis finalise sur done', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        { event: 'token', data: { content: 'Hel' } },
        { event: 'token', data: { content: 'lo' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const assistant = lastAssistant(api.messages.value);
    expect(assistant?.content).toBe('Hello');
    expect(assistant?.streaming).toBe(false);
    expect(api.streaming.value).toBe(false);
    unmount();
  });

  it('préserve le texte streamé (done n écrase pas le contenu déjà reçu)', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        { event: 'token', data: { content: 'partial' } },
        { event: 'done', data: { content: 'réponse finale' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    // done.content n'écrase plus le flux streamé : on garde le texte réel
    // produit avant les outils (essentiel pour le rendu interleaved).
    expect(lastAssistant(api.messages.value)?.content).toBe('partial');
    unmount();
  });

  it('utilise done.content en fallback quand rien n a été streamé', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([{ event: 'done', data: { content: 'réponse finale' } }]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(lastAssistant(api.messages.value)?.content).toBe('réponse finale');
    unmount();
  });

  it('intercale texte -> outil -> texte selon l ordre des events', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        { event: 'token', data: { content: 'Avant ' } },
        {
          event: 'tool_call_start',
          data: { tool_call_id: 't1', tool_name: 'list_files', arguments: {} },
        },
        {
          event: 'tool_call_result',
          data: { tool_call_id: 't1', tool_name: 'list_files', result: { entries: [] }, is_error: false },
        },
        { event: 'token', data: { content: 'Après' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const assistant = lastAssistant(api.messages.value);
    const parts = assistant?.parts ?? [];
    expect(parts.map((p) => p.type)).toEqual(['text', 'tool_call', 'text']);
    expect((parts[0] as { content: string }).content).toBe('Avant ');
    expect((parts[2] as { content: string }).content).toBe('Après');
    expect(assistant?.content).toBe('Avant Après');
    unmount();
  });

  it('trace les tool_calls : running puis success', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'tool_call_start',
          data: { tool_call_id: 't1', tool_name: 'read_document', arguments: { document_id: 'a' } },
        },
        {
          event: 'tool_call_result',
          data: { tool_call_id: 't1', tool_name: 'read_document', result: { text: 'x' }, is_error: false },
        },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const tool = lastAssistant(api.messages.value)?.toolCalls?.[0];
    expect(tool?.status).toBe('success');
    expect(tool?.endedAt).toBeTypeOf('number');
    expect(tool?.result).toEqual({ text: 'x' });
    unmount();
  });

  it('mappe humanSummary depuis human_summary (snake_case)', () => {
    const start = mapPythonSseEvent({
      type: 'tool_call_start',
      data: {
        tool_call_id: 't1',
        tool_name: 'list_files',
        human_summary: 'Liste des fichiers du projet',
      },
    });
    expect(start.data.humanSummary).toBe('Liste des fichiers du projet');

    const result = mapPythonSseEvent({
      type: 'tool_call_result',
      data: {
        tool_call_id: 't1',
        human_summary: '3 fichiers trouvés',
        result: {},
        is_error: false,
      },
    });
    expect(result.data.humanSummary).toBe('3 fichiers trouvés');
  });

  it('applique humanSummary au tool call (start puis remplacement au result)', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'tool_call_start',
          data: {
            tool_call_id: 't1',
            tool_name: 'list_files',
            arguments: {},
            human_summary: 'Je liste les fichiers',
          },
        },
        {
          event: 'tool_call_result',
          data: {
            tool_call_id: 't1',
            tool_name: 'list_files',
            result: { entries: [] },
            is_error: false,
            human_summary: '12 fichiers listés',
          },
        },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const tool = lastAssistant(api.messages.value)?.toolCalls?.[0];
    expect(tool?.humanSummary).toBe('12 fichiers listés');
    unmount();
  });

  it('marque un tool_call en erreur quand is_error est vrai', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        { event: 'tool_call_start', data: { tool_call_id: 't1', tool_name: 'run_code', arguments: {} } },
        {
          event: 'tool_call_result',
          data: { tool_call_id: 't1', tool_name: 'run_code', result: { error: 'boom' }, is_error: true },
        },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(lastAssistant(api.messages.value)?.toolCalls?.[0]?.status).toBe('error');
    unmount();
  });

  it('sur un event error SSE, attache une erreur localisée au message + au ref global', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'error',
          data: { code: 'max_iterations_reached', message: 'Maximum agent iterations reached before final answer.' },
        },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const assistant = lastAssistant(api.messages.value);
    expect(assistant?.error?.code).toBe('max_iterations_reached');
    expect(assistant?.error?.message).toContain("limite d'itérations");
    expect(assistant?.error?.retryable).toBe(true);
    expect(assistant?.streaming).toBe(false);
    expect(api.error.value?.code).toBe('max_iterations_reached');
    expect(api.error.value?.retryable).toBe(true);
    unmount();
  });

  it('classifie un échec fetch en sidecar_unreachable (réessayable)', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new TypeError('Failed to fetch'),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(api.error.value?.code).toBe('sidecar_unreachable');
    expect(api.error.value?.retryable).toBe(true);
    expect(api.error.value?.message).toContain("service IA n'est pas accessible");
    expect(lastAssistant(api.messages.value)?.error?.code).toBe('sidecar_unreachable');
    unmount();
  });

  it('classifie un HTTP non-2xx en sidecar_unreachable', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([], { ok: false, status: 503 }),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(api.error.value?.code).toBe('sidecar_unreachable');
    unmount();
  });

  it('refuse l envoi sans dossier projet (no_project, non réessayable)', async () => {
    const { api, unmount } = mountStream(null);
    await api.send('hi');

    expect(api.error.value?.code).toBe('no_project');
    expect(api.error.value?.retryable).toBe(false);
    expect(api.messages.value).toHaveLength(0);
    unmount();
  });

  it('mappe confirmation_request', () => {
    const mapped = mapPythonSseEvent({
      type: 'confirmation_request',
      data: {
        confirmation_id: 'cf_1',
        tool_call_id: 'tc_1',
        tool_name: 'generate_document',
        action: 'create',
        proposed_path: 'contrat_dupont.docx',
        human_summary: 'Je vais créer contrat_dupont.docx',
      },
    });
    expect(mapped.type).toBe('confirmation_request');
    expect(mapped.data.confirmationId).toBe('cf_1');
    expect(mapped.data.toolCallId).toBe('tc_1');
    expect(mapped.data.action).toBe('create');
    expect(mapped.data.proposedPath).toBe('contrat_dupont.docx');
    expect(mapped.data.humanSummary).toBe('Je vais créer contrat_dupont.docx');
  });

  it('mappe turn_start et propage turn_id jusqu\'au confirm', async () => {
    const mapped = mapPythonSseEvent({
      type: 'turn_start',
      data: { turn_id: 'turn_abc' },
    });
    expect(mapped.type).toBe('turn_start');
    expect(mapped.data.turnId).toBe('turn_abc');

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      sseResponse([
        { event: 'turn_start', data: { turn_id: 'turn_abc' } },
        {
          event: 'tool_call_start',
          data: { tool_call_id: 'tc_1', tool_name: 'generate_document' },
        },
        {
          event: 'confirmation_request',
          data: {
            confirmation_id: 'cf_1',
            tool_call_id: 'tc_1',
            tool_name: 'generate_document',
            action: 'create',
            proposed_path: 'contrat.docx',
            human_summary: 'Je vais créer contrat.docx',
            turn_id: 'turn_abc',
          },
        },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const assistant = lastAssistant(api.messages.value);
    expect(assistant?.pendingConfirmation?.turnId).toBe('turn_abc');

    // Second appel fetch = POST /agent/confirm.
    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 200 }));
    await api.confirm('approve');

    const confirmBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(confirmBody.confirmation_id).toBe('cf_1');
    expect(confirmBody.decision).toBe('approve');
    expect(confirmBody.turn_id).toBe('turn_abc');
    unmount();
  });

  it('pose awaiting_confirmation puis efface pendingConfirmation au result', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'tool_call_start',
          data: {
            tool_call_id: 'tc_1',
            tool_name: 'generate_document',
            arguments: { name: 'contrat.docx' },
          },
        },
        {
          event: 'confirmation_request',
          data: {
            confirmation_id: 'cf_1',
            tool_call_id: 'tc_1',
            tool_name: 'generate_document',
            action: 'create',
            proposed_path: 'contrat.docx',
            human_summary: 'Je vais créer contrat.docx',
          },
        },
        {
          event: 'tool_call_result',
          data: {
            tool_call_id: 'tc_1',
            tool_name: 'generate_document',
            result: { metadata: { path: 'contrat.docx' } },
            is_error: false,
          },
        },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const assistant = lastAssistant(api.messages.value);
    const tool = assistant?.toolCalls?.[0];
    expect(tool?.status).toBe('success');
    expect(assistant?.pendingConfirmation).toBeNull();
    unmount();
  });

  it('retry renvoie le dernier message et déduplique la paire user+assistant', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'ok' } },
          { event: 'done', data: { content: '' } },
        ]),
      );

    const { api, unmount } = mountStream();
    await api.send('hi');
    // Premier tour : échec -> 1 user + 1 assistant en erreur.
    expect(api.messages.value).toHaveLength(2);
    expect(api.error.value?.code).toBe('sidecar_unreachable');

    await api.retry();
    // Second tour : la paire échouée a été retirée puis recréée -> toujours 2.
    expect(api.messages.value).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(api.error.value).toBeNull();
    expect(lastAssistant(api.messages.value)?.content).toBe('ok');
    expect(lastAssistant(api.messages.value)?.error).toBeUndefined();
    unmount();
  });

  it('mappe et applique thinking_start/delta/end en bloc raisonnement', async () => {
    const start = mapPythonSseEvent({
      type: 'thinking_start',
      data: { type: 'thinking_start', thinking_id: 'think-0' },
    });
    expect(start.type).toBe('thinking_start');
    expect(start.data.thinkingId).toBe('think-0');

    const delta = mapPythonSseEvent({
      type: 'thinking_delta',
      data: { type: 'thinking_delta', thinking_id: 'think-0', content: 'Je réfléchis' },
    });
    expect(delta.data.content).toBe('Je réfléchis');

    const end = mapPythonSseEvent({
      type: 'thinking_end',
      data: { type: 'thinking_end', thinking_id: 'think-0' },
    });
    expect(end.type).toBe('thinking_end');

    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        { event: 'thinking_start', data: { type: 'thinking_start', thinking_id: 'think-0' } },
        {
          event: 'thinking_delta',
          data: { type: 'thinking_delta', thinking_id: 'think-0', content: 'Étape 1' },
        },
        {
          event: 'thinking_delta',
          data: { type: 'thinking_delta', thinking_id: 'think-0', content: ' puis 2' },
        },
        { event: 'thinking_end', data: { type: 'thinking_end', thinking_id: 'think-0' } },
        { event: 'token', data: { content: 'Réponse' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    const assistant = lastAssistant(api.messages.value);
    const thinkingPart = assistant?.parts?.find((p) => p.type === 'thinking');
    expect(thinkingPart).toMatchObject({
      type: 'thinking',
      thinkingId: 'think-0',
      content: 'Étape 1 puis 2',
      done: true,
    });
    expect(assistant?.thinking).toBe('Étape 1 puis 2');
    expect(assistant?.parts?.map((p) => p.type)).toEqual(['text', 'thinking', 'text']);
    unmount();
  });

  it('reset error au loadMessages après une erreur précédente', () => {
    const { api, unmount } = mountStream();
    api.error.value = {
      code: 'sidecar_unreachable',
      message: 'Erreur',
      retryable: true,
    };

    api.loadMessages([
      {
        id: 'm1',
        role: 'user',
        content: 'hello',
        createdAt: new Date().toISOString(),
      },
    ]);

    expect(api.error.value).toBeNull();
    unmount();
  });

  it('applyStreamEvent crée un ChatThinkingPart via les events unitaires', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a1',
        role: 'assistant',
        content: '',
        streaming: true,
        parts: [{ type: 'text', id: 't1', content: '' }],
        createdAt: new Date().toISOString(),
      },
    ];

    applyStreamEvent(messages, 'a1', {
      type: 'thinking_start',
      data: { thinkingId: 'think-0' },
    });
    applyStreamEvent(messages, 'a1', {
      type: 'thinking_delta',
      data: { thinkingId: 'think-0', content: 'Analyse' },
    });
    applyStreamEvent(messages, 'a1', {
      type: 'thinking_end',
      data: { thinkingId: 'think-0' },
    });

    const part = messages[0].parts?.find((p) => p.type === 'thinking');
    expect(part).toMatchObject({
      type: 'thinking',
      thinkingId: 'think-0',
      content: 'Analyse',
      done: true,
    });
    expect(messages[0].thinking).toBe('Analyse');
  });
});

describe('mergeLlmConfigsWithSessionReasoning', () => {
  it('clampe un override `low` vers none pour mistral-small-latest', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: {
          provider: 'mistral',
          model: 'mistral-small-latest',
          reasoning_effort: 'high',
        },
        embedding: null,
      },
      'low',
    );
    expect(merged.chat?.reasoning_effort).toBeUndefined();
  });

  it('clampe un override `medium` vers none pour mistral-small-latest', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-small-latest' },
        embedding: null,
      },
      'medium',
    );
    expect(merged.chat?.reasoning_effort).toBeUndefined();
  });

  it('supprime reasoning_effort quand l override clampé vaut none', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-small-latest' },
        embedding: null,
      },
      'none',
    );
    expect(merged.chat?.reasoning_effort).toBeUndefined();
  });

  it('garde low pour un modèle qui le supporte', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-medium-latest' },
        embedding: null,
      },
      'low',
    );
    expect(merged.chat?.reasoning_effort).toBe('low');
  });

  it('ignore l override si le modèle ne supporte pas le raisonnement', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'ollama', model: 'llama3' },
        embedding: null,
      },
      'low',
    );
    expect(merged.chat?.reasoning_effort).toBeUndefined();
  });
});
