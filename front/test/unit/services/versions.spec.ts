import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@services/aiSidecar', () => ({
  getAiSidecarUrl: () => 'http://127.0.0.1:8765',
  getDesktopSecret: () => 'desktop-dev-secret',
}));

import { listVersions, restoreVersion } from '@services/versions';

describe('versions service', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('listVersions appelle GET /versions avec les bons paramètres', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshots: [
          {
            original_path: 'doc.txt',
            snapshot_path: '.workproba/versions/sess-1/snap.txt',
            timestamp: '2026-01-01T00:00:00Z',
            session_id: 'sess-1',
          },
        ],
      }),
    });

    const snapshots = await listVersions('/proj', 'sess-1', 'doc.txt');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/versions?project_path=%2Fproj&session_id=sess-1&file_path=doc.txt',
      { headers: { 'X-Internal-Secret': 'desktop-dev-secret' } },
    );
    expect(snapshots).toHaveLength(1);
    expect(snapshots[0].snapshot_path).toContain('.workproba/versions');
  });

  it('restoreVersion appelle POST /versions/restore', async () => {
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        restored_path: 'doc.txt',
        snapshot_path: '.workproba/versions/sess-1/snap.txt',
      }),
    });

    const result = await restoreVersion(
      '/proj',
      'sess-1',
      '.workproba/versions/sess-1/snap.txt',
    );

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8765/versions/restore',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-Internal-Secret': 'desktop-dev-secret',
        }),
        body: JSON.stringify({
          project_path: '/proj',
          session_id: 'sess-1',
          snapshot_path: '.workproba/versions/sess-1/snap.txt',
        }),
      }),
    );
    expect(result.restored_path).toBe('doc.txt');
  });
});
