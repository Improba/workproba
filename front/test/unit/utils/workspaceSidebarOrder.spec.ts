import { describe, expect, it } from 'vitest';
import type { WorkspaceInfo } from '@composables/useDesktop.types';
import {
  applySidebarOrder,
  orderIdsFromWorkspaces,
  removeFromSidebarOrder,
} from '@utils/workspaceSidebarOrder';

function workspace(id: string, lastOpenedAt: string): WorkspaceInfo {
  return {
    id,
    folderPath: `/tmp/${id}`,
    dataDir: `/data/${id}`,
    title: id,
    createdAt: '2026-01-01T00:00:00Z',
    lastOpenedAt,
  };
}

describe('workspaceSidebarOrder', () => {
  it('applique l\'ordre sauvegardé puis complète par lastOpenedAt', () => {
    const workspaces = [
      workspace('ws_a', '2026-01-03T00:00:00Z'),
      workspace('ws_b', '2026-01-02T00:00:00Z'),
      workspace('ws_c', '2026-01-01T00:00:00Z'),
    ];

    expect(applySidebarOrder(workspaces, ['ws_c', 'ws_a']).map((item) => item.id)).toEqual([
      'ws_c',
      'ws_a',
      'ws_b',
    ]);
  });

  it('retourne les ids dans l\'ordre affiché', () => {
    const workspaces = [workspace('ws_a', '2026-01-01T00:00:00Z')];
    expect(orderIdsFromWorkspaces(workspaces)).toEqual(['ws_a']);
  });

  it('ignore les ids obsolètes dans l\'ordre sauvegardé', () => {
    const workspaces = [
      workspace('ws_a', '2026-01-03T00:00:00Z'),
      workspace('ws_b', '2026-01-02T00:00:00Z'),
    ];

    expect(applySidebarOrder(workspaces, ['ws_z', 'ws_a']).map((item) => item.id)).toEqual([
      'ws_a',
      'ws_b',
    ]);
  });

  it('retombe sur lastOpenedAt sans ordre sauvegardé', () => {
    const workspaces = [
      workspace('ws_a', '2026-01-01T00:00:00Z'),
      workspace('ws_b', '2026-01-03T00:00:00Z'),
    ];

    expect(applySidebarOrder(workspaces, null).map((item) => item.id)).toEqual(['ws_b', 'ws_a']);
  });
});
