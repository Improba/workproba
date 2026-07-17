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
    confirmBeforeWriteEffective: ref(true),
    codeExecute: ref(true),
    auditEnabled: ref(null),
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

  it('mappe memory_citations vers des citations structurées', () => {
    const mapped = mapPythonSseEvent({
      type: 'memory_citations',
      data: {
        citations: [
          {
            id: 'mem-1',
            snippet: 'Budget Q3 validé',
            source: 'manual',
            scope: 'project',
          },
        ],
      },
    });
    expect(mapped?.type).toBe('memory_citations');
    expect(mapped?.data.citations).toEqual([
      {
        id: 'mem-1',
        snippet: 'Budget Q3 validé',
        source: 'manual',
        scope: 'project',
      },
    ]);
  });

  it('mappe work_started et ignore les autres work_* sans crasher', () => {
    const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const started = mapPythonSseEvent({
      type: 'work_started',
      data: { work_id: 'turn-1', objective: 'hello' },
    });
    expect(started?.type).toBe('work_started');
    expect(started?.data.workId).toBe('turn-1');
    expect(
      mapPythonSseEvent({
        type: 'work_contribution',
        data: {
          work_id: 'turn-1',
          contribution_id: 'tc1',
          kind: 'capability',
          label: 'Capability',
          status: 'started',
        },
      }),
    ).toBeNull();
    debugSpy.mockRestore();
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

  it('confirmation_timeout ne termine pas le streaming ni assistant.error', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a1',
        role: 'assistant',
        content: '',
        streaming: true,
        toolCalls: [
          {
            id: 'tc_1',
            name: 'write_docx',
            status: 'awaiting_confirmation',
          },
        ],
        pendingConfirmation: {
          confirmationId: 'cf_1',
          toolCallId: 'tc_1',
          toolName: 'write_docx',
          action: 'create',
          proposedPath: 'out.docx',
          humanSummary: 'Créer out.docx',
        },
      },
    ];

    applyStreamEvent(messages, 'a1', {
      type: 'error',
      data: {
        code: 'confirmation_timeout',
        message: "La confirmation a expiré. Relancez l'action si nécessaire.",
      },
    });

    const assistant = messages[0];
    expect(assistant.streaming).toBe(true);
    expect(assistant.error).toBeUndefined();
    expect(assistant.pendingConfirmation).toBeNull();
    expect(assistant.toolCalls?.[0]?.status).toBe('error');
    expect(assistant.toolCalls?.[0]?.humanSummary).toContain('expiré');
    expect(assistant.toolCalls?.[0]?.endedAt).toBeTypeOf('number');
  });

  it('continue le stream SSE après confirmation_timeout', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'tool_call_start',
          data: { tool_call_id: 'tc_1', tool_name: 'write_docx', arguments: {} },
        },
        {
          event: 'confirmation_request',
          data: {
            confirmation_id: 'cf_1',
            tool_call_id: 'tc_1',
            tool_name: 'write_docx',
            action: 'create',
            proposed_path: 'out.docx',
            human_summary: 'Créer out.docx',
          },
        },
        {
          event: 'error',
          data: { code: 'confirmation_timeout', message: 'expiré' },
        },
        { event: 'token', data: { content: 'suite' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(lastAssistant(api.messages.value)?.content).toBe('suite');
    expect(api.streaming.value).toBe(false);
    expect(api.error.value).toBeNull();
    unmount();
  });

  it('plan_timeout efface pendingPlan sans bannière error', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a1',
        role: 'assistant',
        content: '',
        streaming: true,
        pendingPlan: {
          planId: 'plan-1',
          steps: [{ tool: 'write_docx', summary: 'écrire', target: 'a.docx' }],
          rationale: 'parce que',
          status: 'pending',
        },
      },
    ];

    applyStreamEvent(messages, 'a1', {
      type: 'error',
      data: {
        code: 'plan_timeout',
        message: 'Le plan a expiré.',
      },
    });

    expect(messages[0].streaming).toBe(true);
    expect(messages[0].error).toBeUndefined();
    expect(messages[0].pendingPlan).toBeNull();
  });

  it('continue le stream SSE après plan_timeout sans error.value', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'plan_proposed',
          data: {
            plan_id: 'plan-1',
            rationale: 'r',
            steps: [{ tool: 'write_docx', summary: 'écrire', target: 'a.docx' }],
          },
        },
        {
          event: 'error',
          data: { code: 'plan_timeout', message: 'expiré' },
        },
        { event: 'token', data: { content: 'après plan' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('hi');

    expect(lastAssistant(api.messages.value)?.content).toBe('après plan');
    expect(lastAssistant(api.messages.value)?.pendingPlan).toBeNull();
    expect(api.error.value).toBeNull();
    unmount();
  });

  it('abort après confirmation permet un nouvel envoi', async () => {
    const encoder = new TextEncoder();
    const confirmationEvents = [
      {
        event: 'confirmation_request',
        data: {
          confirmation_id: 'cf_1',
          tool_call_id: 'tc_1',
          tool_name: 'write_docx',
          action: 'create',
          proposed_path: 'out.docx',
          human_summary: 'Créer out.docx',
        },
      },
    ]
      .map(
        (e) =>
          `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`,
      )
      .join('');

    const hangingBody = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(confirmationEvents));
      },
      pull() {
        return new Promise(() => {});
      },
    });

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: hangingBody,
      headers: new Headers(),
    } as Response);
    fetchMock.mockResolvedValueOnce(
      sseResponse([
        { event: 'token', data: { content: 'ok' } },
        { event: 'done', data: { content: '' } },
      ]),
    );

    const { api, unmount } = mountStream();
    void api.send('hi');
    await Promise.resolve();
    await Promise.resolve();
    api.abort();
    await api.send('again');

    expect(lastAssistant(api.messages.value)?.content).toBe('ok');
    unmount();
  });

  it('refus de confirmation via tool_call_result : statut error et résumé annulé', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a1',
        role: 'assistant',
        content: '',
        streaming: true,
        toolCalls: [
          {
            id: 'tc_1',
            name: 'generate_document',
            status: 'awaiting_confirmation',
            startedAt: 1000,
          },
        ],
        pendingConfirmation: {
          confirmationId: 'cf_1',
          toolCallId: 'tc_1',
          toolName: 'generate_document',
          action: 'create',
          proposedPath: 'note.md',
          humanSummary: 'Je vais créer note.md',
        },
      },
    ];

    applyStreamEvent(messages, 'a1', {
      type: 'tool_call_result',
      data: {
        id: 'tc_1',
        name: 'generate_document',
        result: { content: 'workproba:approval_denied Action refusée.' },
        error: true,
        status: 'error',
        humanSummary: 'Action annulée',
      },
    });

    const assistant = messages[0];
    expect(assistant.pendingConfirmation).toBeNull();
    expect(assistant.toolCalls?.[0]?.status).toBe('error');
    expect(assistant.toolCalls?.[0]?.humanSummary).toBe('Action annulée');
    expect(assistant.toolCalls?.[0]?.endedAt).toBeTypeOf('number');
  });

  it('internal_error garde le comportement terminal sur error SSE', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a1',
        role: 'assistant',
        content: '',
        streaming: true,
      },
    ];

    applyStreamEvent(messages, 'a1', {
      type: 'error',
      data: {
        code: 'internal_error',
        message: 'Erreur interne',
      },
    });

    const assistant = messages[0];
    expect(assistant.streaming).toBe(false);
    expect(assistant.error?.code).toBe('internal_error');
    expect(assistant.error?.retryable).toBe(true);
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
        effect: 'create',
        targets: ['contrat_dupont.docx'],
        headline: 'Je vais Créer : contrat_dupont.docx',
        protection_labels: ['Aperçu disponible avant validation'],
      },
    });
    expect(mapped.type).toBe('confirmation_request');
    expect(mapped.data.confirmationId).toBe('cf_1');
    expect(mapped.data.toolCallId).toBe('tc_1');
    expect(mapped.data.action).toBe('create');
    expect(mapped.data.proposedPath).toBe('contrat_dupont.docx');
    expect(mapped.data.humanSummary).toBe('Je vais créer contrat_dupont.docx');
    expect(mapped.data.effect).toBe('create');
    expect(mapped.data.targets).toEqual(['contrat_dupont.docx']);
    expect(mapped.data.headline).toBe('Je vais Créer : contrat_dupont.docx');
    expect(mapped.data.protectionLabels).toEqual(['Aperçu disponible avant validation']);
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
    expect(confirmBody.locale).toBe('fr');
    unmount();
  });

  it('mappe work_started et expose streamCorrelation', async () => {
    const mapped = mapPythonSseEvent({
      type: 'work_started',
      data: { work_id: 'turn_corr', objective: 'Analyser le budget' },
    });
    expect(mapped?.type).toBe('work_started');
    expect(mapped?.data.workId).toBe('turn_corr');

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(
      sseResponse([
        { event: 'turn_start', data: { turn_id: 'turn_corr' } },
        { event: 'work_started', data: { work_id: 'turn_corr', objective: 'Budget' } },
        { event: 'done', data: { content: 'ok' } },
      ]),
    );

    const { api, unmount } = mountStream();
    await api.send('budget');

    expect(api.streamCorrelation.value).toEqual({
      turnId: 'turn_corr',
      workId: 'turn_corr',
    });
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
      subject: expect.any(String),
      summary: expect.any(String),
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

  it('loadMessages réinitialise le contexte retry', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new TypeError('Failed to fetch'),
    );

    const { api, unmount } = mountStream();
    await api.send('ancien message');
    expect(api.error.value?.code).toBe('sidecar_unreachable');

    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockClear();

    api.loadMessages([
      {
        id: 'm1',
        role: 'user',
        content: 'nouvelle session',
        createdAt: new Date().toISOString(),
      },
    ]);

    await api.retry();
    expect(fetchMock).not.toHaveBeenCalled();
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

  it('mappe fallback SSE vers ChatStreamFallbackData', () => {
    const mapped = mapPythonSseEvent({
      type: 'fallback',
      data: {
        turn_id: 'turn-1',
        from_provider: 'mistral',
        to_provider: 'ollama',
        from_model: 'mistral-small-latest',
        to_model: 'llama3.2',
        reason: 'timeout',
      },
    });
    expect(mapped?.type).toBe('fallback');
    expect(mapped?.data).toMatchObject({
      turnId: 'turn-1',
      fromProvider: 'mistral',
      toProvider: 'ollama',
      fromModel: 'mistral-small-latest',
      toModel: 'llama3.2',
      reason: 'timeout',
    });
  });

  it('applyCompactionToMessages réduit les messages et insère un résumé user', () => {
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
    expect(messages[0].role).toBe('user');
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

  it('applyCompactionToMessages remplace un résumé antérieur quand un nouveau arrive', () => {
    const priorSummary: ChatMessage = {
      id: 'prior-sum',
      role: 'system',
      content: 'Résumé des échanges précédents :\n\nAncien',
      messageKind: 'compaction',
      createdAt: '2026-01-01T00:00:00.000Z',
    };
    const messages: ChatMessage[] = [
      priorSummary,
      { id: 'm1', role: 'user', content: 'msg 1', createdAt: '2026-01-01T00:00:01.000Z' },
      { id: 'm2', role: 'assistant', content: 'msg 2', createdAt: '2026-01-01T00:00:02.000Z' },
      { id: 'cur-u', role: 'user', content: 'tour', createdAt: '2026-01-01T00:00:03.000Z' },
      {
        id: 'cur-a',
        role: 'assistant',
        content: '',
        streaming: true,
        createdAt: '2026-01-01T00:00:04.000Z',
      },
    ];

    applyCompactionToMessages(messages, {
      dropped_count: 1,
      kept_count: 0,
      summary: 'Nouveau résumé',
      truncated: false,
    });

    expect(messages.filter((m) => m.messageKind === 'compaction')).toHaveLength(1);
    expect(messages[0].content).toContain('Nouveau résumé');
    expect(messages[0].id).not.toBe('prior-sum');
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
      subject: 'Analyse',
      summary: 'Analyse',
    });
    expect(messages[0].thinking).toBe('Analyse');
  });

  it('thinking_delta sans thinking_start crée quand même la part', () => {
    const messages: ChatMessage[] = [
      {
        id: 'a1',
        role: 'assistant',
        content: '',
        streaming: true,
        parts: [{ type: 'text', id: 't1', content: 'déjà du texte' }],
        createdAt: new Date().toISOString(),
      },
    ];

    applyStreamEvent(messages, 'a1', {
      type: 'thinking_delta',
      data: { thinkingId: 'think-orphan', content: 'orphan delta' },
    });
    applyStreamEvent(messages, 'a1', {
      type: 'thinking_end',
      data: { thinkingId: 'think-orphan' },
    });

    const part = messages[0].parts?.find((p) => p.type === 'thinking');
    expect(part).toMatchObject({
      type: 'thinking',
      thinkingId: 'think-orphan',
      content: 'orphan delta',
      done: true,
    });
    expect(messages[0].thinking).toBe('orphan delta');
  });

  it('met à jour le subject pendant thinking_delta (throttle)', () => {
    vi.useFakeTimers();
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
      data: { thinkingId: 'think-0', content: 'Première étape\n' },
    });
    applyStreamEvent(messages, 'a1', {
      type: 'thinking_delta',
      data: { thinkingId: 'think-0', content: 'Deuxième étape' },
    });

    const part = messages[0].parts?.find((p) => p.type === 'thinking');
    expect(part?.subject).toBeUndefined();

    vi.advanceTimersByTime(300);
    expect(part).toMatchObject({
      content: 'Première étape\nDeuxième étape',
      done: false,
      subject: 'Deuxième étape',
    });
    expect(part?.summary).toBeUndefined();
    vi.useRealTimers();
  });
});

describe('mergeLlmConfigsWithSessionReasoning', () => {
  it('clampe un override `low` vers high pour mistral-small-latest', () => {
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
    expect(merged.chat?.reasoning_effort).toBe('high');
  });

  it('clampe un override `medium` vers high pour mistral-small-latest', () => {
    const merged = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-small-latest' },
        embedding: null,
      },
      'medium',
    );
    expect(merged.chat?.reasoning_effort).toBe('high');
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

  it('clampe low/medium vers high pour mistral-medium (API binaire)', () => {
    const mergedLow = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-medium-latest' },
        embedding: null,
      },
      'low',
    );
    expect(mergedLow.chat?.reasoning_effort).toBe('high');

    const mergedMedium = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-medium-latest' },
        embedding: null,
      },
      'medium',
    );
    expect(mergedMedium.chat?.reasoning_effort).toBe('high');

    const mergedHigh = mergeLlmConfigsWithSessionReasoning(
      {
        chat: { provider: 'mistral', model: 'mistral-medium-latest' },
        embedding: null,
      },
      'high',
    );
    expect(mergedHigh.chat?.reasoning_effort).toBe('high');
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

describe('useChatStream — browser tool results', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('appelle onBrowserToolCall pour browser_click avec bbox', async () => {
    const onBrowserToolCall = vi.fn();
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'tool_call_start',
          data: {
            tool_call_id: 'tc_browser_1',
            tool_name: 'browser_click',
            arguments: { ref: 'e9' },
          },
        },
        {
          event: 'tool_call_result',
          data: {
            tool_call_id: 'tc_browser_1',
            tool_name: 'browser_click',
            result: {
              snapshot_yaml: '- button [ref=e9]',
              screenshot_b64: 'abc',
              action_ref: 'e9',
              action_bbox: { x: 10, y: 20, width: 100, height: 32 },
              viewport: { width: 1280, height: 720 },
            },
            is_error: false,
          },
        },
        { event: 'done', data: { content: '' } },
      ]),
    );

    let api!: UseChatStreamReturn;
    const wrapper = mount(
      defineComponent({
        setup() {
          api = useChatStream({
            sessionId: ref('sess-1'),
            projectPath: ref('/proj'),
            onBrowserToolCall,
          });
          return {};
        },
        template: '<div />',
      }),
    );

    await api.send('clique sur le bouton');
    expect(onBrowserToolCall).toHaveBeenCalledWith(
      'browser_click',
      expect.objectContaining({
        action_ref: 'e9',
        action_bbox: expect.objectContaining({ width: 100 }),
      }),
    );
    wrapper.unmount();
  });

  it('n appelle pas onBrowserToolCall sur erreur browser', async () => {
    const onBrowserToolCall = vi.fn();
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      sseResponse([
        {
          event: 'tool_call_start',
          data: {
            tool_call_id: 'tc_browser_err',
            tool_name: 'browser_click',
            arguments: { ref: 'e9' },
          },
        },
        {
          event: 'tool_call_result',
          data: {
            tool_call_id: 'tc_browser_err',
            tool_name: 'browser_click',
            result: { message: 'browser_session_inactive' },
            is_error: true,
          },
        },
        { event: 'done', data: { content: '' } },
      ]),
    );

    let api!: UseChatStreamReturn;
    const wrapper = mount(
      defineComponent({
        setup() {
          api = useChatStream({
            sessionId: ref('sess-1'),
            projectPath: ref('/proj'),
            onBrowserToolCall,
          });
          return {};
        },
        template: '<div />',
      }),
    );

    await api.send('clique');
    expect(onBrowserToolCall).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('editAndResend tronque depuis le message user et renvoie le texte édité', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R1' } },
          { event: 'done', data: { content: '' } },
        ]),
      )
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R2' } },
          { event: 'done', data: { content: '' } },
        ]),
      )
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R3' } },
          { event: 'done', data: { content: '' } },
        ]),
      );

    const { api, unmount } = mountStream();
    await api.send('premier');
    await api.send('second');
    expect(api.messages.value).toHaveLength(4);

    const firstUserId = api.messages.value[0].id;
    await api.editAndResend(firstUserId, 'premier modifié');

    expect(api.messages.value).toHaveLength(2);
    expect(api.messages.value[0].content).toBe('premier modifié');
    expect(lastAssistant(api.messages.value)?.content).toBe('R3');
    expect(fetchMock).toHaveBeenCalledTimes(3);
    unmount();
  });

  it('regenerateFrom supprime la réponse ciblée et relance le message user précédent', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R1' } },
          { event: 'done', data: { content: '' } },
        ]),
      )
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R2' } },
          { event: 'done', data: { content: '' } },
        ]),
      );

    const { api, unmount } = mountStream();
    await api.send('question');
    const assistantId = lastAssistant(api.messages.value)!.id;

    await api.regenerateFrom(assistantId);

    expect(api.messages.value).toHaveLength(2);
    expect(api.messages.value[0].content).toBe('question');
    expect(lastAssistant(api.messages.value)?.content).toBe('R2');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('retry après échec de regénération conserve le message user', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R1' } },
          { event: 'done', data: { content: '' } },
        ]),
      )
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(
        sseResponse([
          { event: 'token', data: { content: 'R2' } },
          { event: 'done', data: { content: '' } },
        ]),
      );

    const { api, unmount } = mountStream();
    await api.send('question');
    const assistantId = lastAssistant(api.messages.value)!.id;

    await api.regenerateFrom(assistantId);
    expect(api.messages.value).toHaveLength(2);
    expect(api.error.value?.code).toBe('sidecar_unreachable');

    await api.retry();
    expect(api.messages.value).toHaveLength(2);
    expect(api.messages.value[0].content).toBe('question');
    expect(lastAssistant(api.messages.value)?.content).toBe('R2');
    unmount();
  });
});
