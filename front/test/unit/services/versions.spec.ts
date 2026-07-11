import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@services/aiSidecar', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@services/aiSidecar')>();
  return {
    ...actual,
    getAiSidecarUrl: () => 'http://127.0.0.1:8765',
    getDesktopSecret: () => 'desktop-dev-secret',
  };
});

import { listFileVersions, restoreFileVersion } from '@services/aiSidecar';

describe('versions API (aiSidecar)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('listFileVersions appelle GET /versions avec workspace_data_dir', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        versions: [
          {
            version_id: 'v1',
            created_at: '2026-01-01T00:00:00Z',
            size: 120,
            label: 'Avant modification IA',
          },
        ],
      }),
    });

    const versions = await listFileVersions({
      workspaceDataDir: '/data/ws',
      filePath: 'doc.txt',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/versions?workspace_data_dir=%2Fdata%2Fws&file_path=doc.txt',
      { headers: { 'X-Internal-Secret': 'desktop-dev-secret' } },
    );
    expect(versions).toHaveLength(1);
    expect(versions[0].version_id).toBe('v1');
  });

  it('restoreFileVersion appelle POST /versions/restore', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });

    const ok = await restoreFileVersion({
      workspaceDataDir: '/data/ws',
      projectPath: '/data/project',
      filePath: 'doc.txt',
      versionId: 'v1',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/versions/restore',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-Internal-Secret': 'desktop-dev-secret',
        }),
        body: JSON.stringify({
          workspace_data_dir: '/data/ws',
          project_path: '/data/project',
          file_path: 'doc.txt',
          version_id: 'v1',
        }),
      }),
    );
    expect(ok).toBe(true);
  });
});
