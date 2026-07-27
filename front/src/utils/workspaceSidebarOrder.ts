import type { WorkspaceInfo } from '@composables/useDesktop.types';

function sortByLastOpened(workspaces: WorkspaceInfo[]): WorkspaceInfo[] {
  return [...workspaces].sort((left, right) =>
    right.lastOpenedAt.localeCompare(left.lastOpenedAt),
  );
}

export function applySidebarOrder(
  workspaces: WorkspaceInfo[],
  order: string[] | null | undefined,
): WorkspaceInfo[] {
  if (!order?.length) {
    return sortByLastOpened(workspaces);
  }

  const byId = new Map(workspaces.map((workspace) => [workspace.id, workspace]));
  const ordered: WorkspaceInfo[] = [];

  for (const id of order) {
    const workspace = byId.get(id);
    if (!workspace) continue;
    ordered.push(workspace);
    byId.delete(id);
  }

  return [...ordered, ...sortByLastOpened([...byId.values()])];
}

export function orderIdsFromWorkspaces(workspaces: WorkspaceInfo[]): string[] {
  return workspaces.map((workspace) => workspace.id);
}

export function removeFromSidebarOrder(
  order: string[] | null | undefined,
  workspaceId: string,
): string[] {
  return (order ?? []).filter((id) => id !== workspaceId);
}
