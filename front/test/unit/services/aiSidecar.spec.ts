import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  buildAgentTurnPayload,
  fetchDocumentPreview,
  isSafeRelativePath,
  resolveUiMode,
  truncateToolResult,
  MAX_TOOL_RESULT_HISTORY_CHARS,
} from '@services/aiSidecar';

describe('aiSidecar payload', () => {
  it('resolveUiMode renvoie locked si settingsLocked', () => {
    expect(resolveUiMode(true, 'guided')).toBe('locked');
    expect(resolveUiMode(true, 'advanced')).toBe('locked');
  });

  it('resolveUiMode reprend settingsMode sinon', () => {
    expect(resolveUiMode(false, 'guided')).toBe('guided');
    expect(resolveUiMode(false, 'advanced')).toBe('advanced');
  });

  it('buildAgentTurnPayload inclut ui_mode', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'guided',
    );
    expect(payload.ui_mode).toBe('guided');
  });

  it('buildAgentTurnPayload inclut provider_set quand fourni', () => {
    const set = {
      id: 'mistral-default',
      name: 'Mistral',
      description: '',
      badges: [],
      chat: { provider: 'mistral', model: 'mistral-small-latest', reasoning: 'auto' as const },
      embeddings: null,
      ocr: null,
      vision: { mode: 'chat' as const },
      capabilities: { reasoning: 'medium' as const, vision: true, tools: true },
      isDefault: true,
      isBuiltin: true,
    };
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'guided',
      null,
      true,
      [],
      'fr',
      set,
    );
    expect(payload.provider_set).toBeDefined();
    expect(payload.provider_set?.id).toBe('mistral-default');
    expect(payload.llm_provider_config).toBeUndefined();
  });

  it('buildAgentTurnPayload inclut active_plugins quand fourni', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'guided',
      null,
      true,
      [],
      'fr',
      null,
      ['workproba.projet'],
    );
    expect(payload.active_plugins).toEqual(['workproba.projet']);
  });

  it('buildAgentTurnPayload omet active_plugins si liste vide', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'guided',
      null,
      true,
      [],
      'fr',
      null,
      [],
    );
    expect(payload.active_plugins).toBeUndefined();
  });

  it('buildAgentTurnPayload inclut plugin_data_dir quand fourni', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'guided',
      null,
      true,
      [],
      'fr',
      null,
      ['workproba.projet'],
      '/data/plugins/workproba.projet',
    );
    expect(payload.plugin_data_dir).toBe('/data/plugins/workproba.projet');
  });

  it('buildAgentTurnPayload inclut workspace_title quand fourni', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      '/data/ws',
      'kaggle',
    );
    expect(payload.workspace_data_dir).toBe('/data/ws');
    expect(payload.workspace_title).toBe('kaggle');
  });

  it('buildAgentTurnPayload inclut le contexte sécurité preset', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'locked',
      null,
      true,
      [],
      'fr',
      null,
      ['workproba.browser'],
      '/data/plugins/workproba.browser',
      { settingsLocked: true, permissionsNetwork: false, locale: 'fr' },
    );
    expect(payload.settings_locked).toBe(true);
    expect(payload.permissions_network).toBe(false);
  });

  it('buildAgentTurnPayload inclut confirm_before_write quand désactivé', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'advanced',
      null,
      true,
      [],
      'fr',
      null,
      null,
      null,
      { settingsLocked: false, permissionsNetwork: true, locale: 'fr' },
      false,
      false,
    );
    expect(payload.confirm_before_write).toBe(false);
  });

  it('buildAgentTurnPayload omet confirm_before_write quand activé', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'advanced',
      null,
      true,
      [],
      'fr',
      null,
      null,
      null,
      { settingsLocked: false, permissionsNetwork: true, locale: 'fr' },
      false,
      true,
    );
    expect(payload.confirm_before_write).toBeUndefined();
  });

  it('buildAgentTurnPayload inclut browser_pilotage_paused quand actif', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [],
      [],
      null,
      null,
      null,
      'guided',
      null,
      true,
      [],
      'fr',
      null,
      ['workproba.browser'],
      '/data/plugins/workproba.browser',
      { settingsLocked: false, permissionsNetwork: true, locale: 'fr' },
      true,
    );
    expect(payload.browser_pilotage_paused).toBe(true);
  });

  it('buildAgentTurnPayload inclut tool_calls et messages tool tronqués', () => {
    const longResult = 'x'.repeat(MAX_TOOL_RESULT_HISTORY_CHARS + 500);
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [
        {
          id: 'm1',
          role: 'assistant',
          content: 'Je lis le fichier',
          thinking: 'analyse en cours',
          toolCalls: [
            {
              id: 'tc1',
              name: 'read_document',
              status: 'success',
              args: { document_id: 'a.txt' },
              result: longResult,
            },
          ],
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
      [],
    );

    expect(payload.history).toHaveLength(2);
    expect(payload.history[0]).toMatchObject({
      role: 'assistant',
      thinking: 'analyse en cours',
      tool_calls: [
        { id: 'tc1', name: 'read_document', arguments: { document_id: 'a.txt' } },
      ],
    });
    expect(payload.history[1]).toMatchObject({
      role: 'tool',
      tool_call_id: 'tc1',
    });
    expect(payload.history[1].content).toBe(truncateToolResult(longResult));
    expect(payload.history[1].content!.length).toBe(MAX_TOOL_RESULT_HISTORY_CHARS + 1);
  });

  it('buildAgentTurnPayload agrège thinking depuis parts si m.thinking est absent', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [
        {
          id: 'm1',
          role: 'assistant',
          content: 'Réponse',
          parts: [
            {
              type: 'thinking',
              id: 'th1',
              thinkingId: 'think-0',
              content: 'raisonnement parts-only',
              done: true,
            },
            { type: 'text', id: 'tx1', content: 'Réponse' },
          ],
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
      [],
    );

    expect(payload.history[0]).toMatchObject({
      role: 'assistant',
      thinking: 'raisonnement parts-only',
    });
  });

  it('buildAgentTurnPayload retire screenshot_b64 des tools browser dans history', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [
        {
          id: 'm1',
          role: 'assistant',
          content: 'Je navigue',
          toolCalls: [
            {
              id: 'tc_browser',
              name: 'browser_navigate',
              status: 'success',
              args: { url: 'https://example.com' },
              result: {
                url: 'https://example.com',
                snapshot_yaml: '- heading: Example',
                screenshot_b64: 'a'.repeat(5000),
              },
            },
          ],
          createdAt: '2026-01-01T00:00:00.000Z',
        },
      ],
      [],
    );
    const toolEntry = payload.history.find((entry) => entry.role === 'tool');
    expect(toolEntry?.content).not.toContain('screenshot_b64');
    expect(toolEntry?.content).toContain('snapshot_yaml');
  });

  it('buildAgentTurnPayload inclut les messages compaction (rôle user)', () => {
    const payload = buildAgentTurnPayload(
      'sess-1',
      '/proj',
      'hello',
      [
        {
          id: 'sum',
          role: 'user',
          content: 'Résumé des échanges précédents :\n\nDécision conservée',
          messageKind: 'compaction',
          createdAt: '2026-01-01T00:00:00.000Z',
        },
        {
          id: 'u1',
          role: 'user',
          content: 'suite',
          createdAt: '2026-01-01T00:00:01.000Z',
        },
      ],
      [],
    );

    expect(payload.history[0]).toMatchObject({
      role: 'user',
      content: 'Résumé des échanges précédents :\n\nDécision conservée',
    });
    expect(payload.history[1]).toMatchObject({ role: 'user', content: 'suite' });
  });
});

describe('documents/preview', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('isSafeRelativePath rejette les chemins absolus et ..', () => {
    expect(isSafeRelativePath('docs/rapport.docx')).toBe(true);
    expect(isSafeRelativePath('/etc/passwd')).toBe(false);
    expect(isSafeRelativePath('../secret.txt')).toBe(false);
  });

  it('fetchDocumentPreview appelle le sidecar avec les bons paramètres', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        type: 'docx',
        title: 'rapport.docx',
        html: '<p>Hello</p>',
      }),
    });

    const result = await fetchDocumentPreview({
      relativePath: 'docs/rapport.docx',
      projectPath: '/proj',
      workspaceDataDir: '/data',
    });

    expect(result.type).toBe('docx');
    expect(result.html).toContain('Hello');
    const calledUrl = String((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]);
    expect(calledUrl).toContain('/documents/preview?');
    expect(calledUrl).toContain('path=docs%2Frapport.docx');
    expect(calledUrl).toContain('project_path=%2Fproj');
    expect(calledUrl).toContain('workspace_data_dir=%2Fdata');
  });
});

describe('memory', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('forgetAllMemory envoie confirmed: true', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });

    const { forgetAllMemory } = await import('@services/aiSidecar');
    const ok = await forgetAllMemory('/data/ws', 'all');
    expect(ok).toBe(true);

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body.confirmed).toBe(true);
    expect(body.workspace_data_dir).toBe('/data/ws');
    expect(body.scope).toBe('all');
  });

  it('forgetAllMemory transmet scope memories et memory_scope user', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });

    const { forgetAllMemory } = await import('@services/aiSidecar');
    await forgetAllMemory('/data/ws', 'memories', 'user');

    const [, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body.scope).toBe('memories');
    expect(body.memory_scope).toBe('user');
  });

  it('promoteSessionMemory appelle /memory/promote-session', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        facts: ['Le budget RH est de 120k€'],
        counts: { ADD: 1 },
        pruned: 0,
      }),
    });

    const { promoteSessionMemory } = await import('@services/aiSidecar');
    const result = await promoteSessionMemory({
      workspaceDataDir: '/data/ws',
      sessionId: 'sess-1',
      summary: 'Discussion budget.',
      locale: 'fr',
    });

    expect(result.facts).toEqual(['Le budget RH est de 120k€']);
    expect(result.counts.ADD).toBe(1);

    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain('/memory/promote-session');
    expect(init?.method).toBe('POST');
    const body = JSON.parse(String(init?.body));
    expect(body.workspace_data_dir).toBe('/data/ws');
    expect(body.session_id).toBe('sess-1');
    expect(body.summary).toBe('Discussion budget.');
    expect(body.locale).toBe('fr');
  });
});
