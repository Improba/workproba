import { defineComponent, ref, type Ref } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks des dépendances réseau/config avant l'import du composable.
vi.mock('@services/aiSidecar', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@services/aiSidecar')>();
  return {
    ...actual,
    getAiSidecarUrl: () => 'http://127.0.0.1:8765',
    getDesktopSecret: () => 'desktop-dev-secret',
    buildAgentTurnPayload: vi.fn(() => ({ message: 'fake' })),
    buildSidecarSecurityContext: vi.fn(() => ({
      settingsLocked: false,
      permissionsNetwork: true,
      locale: 'fr',
    })),
  };
});
vi.mock('@composables/usePlugins', () => ({
  PROJET_PLUGIN_ID: 'workproba.projet',
  PERSONAS_PLUGIN_ID: 'workproba.personas',
  BROWSER_PLUGIN_ID: 'workproba.browser',
  usePlugins: () => ({
    activePluginIds: ref([]),
    getPluginDataDir: vi.fn(async () => null),
  }),
}));
vi.mock('@composables/useAppSettings', () => ({
  buildActiveLlmConfigs: () => ({
    chat: { provider: 'ollama', model: 'llama3', base_url: null, api_key: null },
    embedding: null,
  }),
  buildActiveProviderSet: () => null,
  useAppSettings: () => ({
    locale: ref('fr'),
    settingsLocked: ref(false),
    permissionsNetwork: ref(true),
  }),
}));

import { useChatStream, mapPythonSseEvent, applyStreamEvent, applyCompactionToMessages, applyAttachmentStatusEvent, mergeLlmConfigsWithSessionReasoning, type UseChatStreamReturn } from '@composables/useChatStream';
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
    text: async () => '',
  } as unknown as Response;
}

function httpErrorResponse(
  status: number,
  body: string,
): Response {
  return {
    ok: false,
    status,
    headers: new Headers(),
    text: async () => body,
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
      httpErrorResponse(503, ''),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(api.error.value?.code).toBe('sidecar_unreachable');
    unmount();
  });

  it('mappe HTTP 400 api_key_missing en message i18n explicite', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      httpErrorResponse(
        400,
        JSON.stringify({
          detail: { code: 'api_key_missing', message: 'No API key for openai' },
        }),
      ),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(api.error.value?.code).toBe('api_key_missing');
    expect(api.error.value?.message).toContain('Clé API manquante');
    expect(api.error.value?.retryable).toBe(false);
    expect(lastAssistant(api.messages.value)?.error?.code).toBe('api_key_missing');
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

  it('mappe compaction avec summary et summary_failed', () => {
    const mapped = mapPythonSseEvent({
      type: 'compaction',
      data: {
        dropped_count: 3,
        kept_count: 5,
        summary: 'Résumé condensé',
        summary_failed: false,
        truncated: false,
      },
    });
    expect(mapped?.type).toBe('compaction');
    expect(mapped?.data.summary).toBe('Résumé condensé');
    expect(mapped?.data.summary_failed).toBe(false);
  });

  it('applyCompactionToMessages réduit les messages et insère un résumé system', () => {
    const messages: ChatMessage[] = [
      { id: 'old', role: 'user', content: 'ancien 1', createdAt: '2026-01-01T00:00:00.000Z' },
      { id: 'old2', role: 'assistant', content: 'ancien 2', createdAt: '2026-01-01T00:00:01.000Z' },
      { id: 'cur-u', role: 'user', content: 'tour courant', createdAt: '2026-01-01T00:00:02.000Z' },
      {
        id: 'cur-a',
        role: 'assistant',
        content: '',
        streaming: true,
        createdAt: '2026-01-01T00:00:03.000Z',
      },
    ];

    applyCompactionToMessages(messages, {
      dropped_count: 2,
      kept_count: 0,
      summary: 'Contexte condensé',
      truncated: false,
    });

    expect(messages).toHaveLength(3);
    expect(messages[0].role).toBe('system');
    expect(messages[0].messageKind).toBe('compaction');
    expect(messages[0].content).toContain('Contexte condensé');
    expect(messages[0].content).toContain('Résumé des échanges précédents :');
    expect(messages[1].id).toBe('cur-u');
    expect(messages[2].id).toBe('cur-a');
  });

  it('applyCompactionToMessages préserve le résumé antérieur en fallback sans summary', () => {
    const priorSummary: ChatMessage = {
      id: 'prior-sum',
      role: 'system',
      content: 'Résumé des échanges précédents :\n\nAncien contexte',
      messageKind: 'compaction',
      createdAt: '2026-01-01T00:00:00.000Z',
    };
    const messages: ChatMessage[] = [
      priorSummary,
      { id: 'old', role: 'user', content: 'ancien 1', createdAt: '2026-01-01T00:00:01.000Z' },
      { id: 'old2', role: 'assistant', content: 'ancien 2', createdAt: '2026-01-01T00:00:02.000Z' },
      { id: 'cur-u', role: 'user', content: 'tour courant', createdAt: '2026-01-01T00:00:03.000Z' },
      {
        id: 'cur-a',
        role: 'assistant',
        content: '',
        streaming: true,
        createdAt: '2026-01-01T00:00:04.000Z',
      },
    ];

    applyCompactionToMessages(messages, {
      dropped_count: 3,
      kept_count: 0,
      truncated: true,
      summary_failed: true,
    });

    expect(messages[0].id).toBe('prior-sum');
    expect(messages[0].messageKind).toBe('compaction');
    expect(messages[1].id).toBe('cur-u');
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

describe('attachment_status SSE', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('applyAttachmentStatusEvent stocke status_key et label_locale', () => {
    const statuses: Record<string, { status_key: string; label_locale: string }> = {};
    applyAttachmentStatusEvent(statuses, {
      attachment_id: 'att_1',
      status_key: 'attachments.status.read',
      label_locale: 'Lue (texte)',
    });
    expect(statuses.att_1).toEqual({
      status_key: 'attachments.status.read',
      label_locale: 'Lue (texte)',
    });
  });

  it('accumule attachment_status pendant un tour SSE', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'attachment_status',
          data: {
            message_id: 'sess-1',
            attachment_id: 'att_42',
            status_key: 'attachments.status.word',
            label_locale: 'Lue (Word)',
          },
        },
        { event: 'token', data: { content: 'OK' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi', {
      attachments: [
        {
          id: 'att_42',
          fileName: 'doc.docx',
          mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          sizeBytes: 100,
          kind: 'document',
          status: 'ready',
        },
      ],
    });

    expect(api.attachmentStatuses.value.att_42).toEqual({
      status_key: 'attachments.status.word',
      label_locale: 'Lue (Word)',
    });
    unmount();
  });
});
