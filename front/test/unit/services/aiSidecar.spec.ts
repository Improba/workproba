import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  buildAgentTurnPayload,
  fetchDocumentPreview,
  isSafeRelativePath,
  resolveUiMode,
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
});
