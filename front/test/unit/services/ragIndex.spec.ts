import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  indexWorkspace,
  ragStatusLabel,
  type WorkspaceIndexReport,
} from '@services/aiSidecar';

describe('ragStatusLabel', () => {
  it('retourne un libellé humain quand indexing', () => {
    expect(ragStatusLabel('indexing', null)).toBe('Analyse des documents…');
  });

  it('retourne "Mémoire à jour" quand rien de neuf (tout déjà indexé)', () => {
    const report: WorkspaceIndexReport = {
      project_root: '/p',
      db_path: '/p/memory.db',
      enabled: true,
      scanned: 1,
      indexed: 0,
      unchanged: 1,
      skipped: 0,
      errors: 0,
      total_chars: 0,
      truncated: false,
      truncation_reason: null,
      indexed_paths: [],
      skipped_paths: [],
      error_paths: [],
      metadata: {},
    };
    expect(ragStatusLabel('done', report)).toBe('Mémoire à jour');
  });

  it('mentionne les ajouts quand de nouveaux fichiers sont indexés', () => {
    const report: WorkspaceIndexReport = {
      project_root: '/p',
      db_path: '/p/memory.db',
      enabled: true,
      scanned: 10,
      indexed: 7,
      unchanged: 2,
      skipped: 1,
      errors: 0,
      total_chars: 1234,
      truncated: false,
      truncation_reason: null,
      indexed_paths: [],
      skipped_paths: [],
      error_paths: [],
      metadata: {},
    };
    expect(ragStatusLabel('done', report)).toBe('Mémoire à jour · 7 ajoutés');
  });

  it('mentionne la limite atteinte quand truncated', () => {
    const report: WorkspaceIndexReport = {
      project_root: '/p',
      db_path: null,
      enabled: true,
      scanned: 1,
      indexed: 1,
      unchanged: 0,
      skipped: 0,
      errors: 0,
      total_chars: 1,
      truncated: true,
      truncation_reason: 'max_total_chars',
      indexed_paths: [],
      skipped_paths: [],
      error_paths: [],
      metadata: {},
    };
    expect(ragStatusLabel('done', report)).toContain('limite atteinte');
  });

  it('retourne désactivée quand disabled', () => {
    expect(ragStatusLabel('disabled', null)).toBe('Mémoire désactivée');
  });
});

describe('indexWorkspace', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.stubEnv('AI_SIDECAR_URL', 'http://127.0.0.1:8765');
    vi.stubEnv('DESKTOP_INTERNAL_SECRET', 'desktop-dev-secret');
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('POST vers /agent/index-workspace et décode le rapport', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ project_root: '/p', enabled: true, indexed: 3 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const report = await indexWorkspace({ projectPath: '/p' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://127.0.0.1:8765/agent/index-workspace');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['X-Internal-Secret']).toBe('desktop-dev-secret');
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.project_path).toBe('/p');
    expect(body.paths).toBeNull();
    expect(report.indexed).toBe(3);
  });

  it('transmet les paths en incremental', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ project_root: '/p', enabled: true, indexed: 1 }), {
        status: 200,
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await indexWorkspace({ projectPath: '/p', paths: ['a.txt', 'b.txt'] });

    const body = JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(body.paths).toEqual(['a.txt', 'b.txt']);
  });

  it('lève une erreur sur HTTP non-ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response('boom', { status: 500 })) as unknown as typeof fetch;

    await expect(indexWorkspace({ projectPath: '/p' })).rejects.toThrow(/HTTP 500/);
  });
});
