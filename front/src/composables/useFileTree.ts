import { computed, onScopeDispose, reactive, ref, shallowRef, watch } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { listDirEntries } from '@composables/useDesktop';
import type { LocalDirEntry } from '@composables/useDesktop.types';

export interface FileNode {
  name: string;
  relativePath: string;
  isDir: boolean;
  kind: string;
  depth: number;
  expanded: boolean;
  loaded: boolean;
  loading: boolean;
  /** Chemins enfants (si dossier). */
  children: string[];
  /** État de session : touché pendant la conversation courante. */
  sessionState: 'idle' | 'created' | 'modified';
}

export interface FsChangePayload {
  kind: 'create' | 'modify' | 'delete';
  path: string;
  isDir: boolean;
}

const ROW_HEIGHT = 26;

function makeNode(entry: LocalDirEntry, depth: number): FileNode {
  return reactive({
    name: entry.name,
    relativePath: entry.relativePath,
    isDir: entry.isDir,
    kind: entry.kind,
    depth,
    expanded: false,
    loaded: !entry.isDir,
    loading: false,
    children: [],
    sessionState: 'idle',
  });
}

function parentRelativePath(relativePath: string): string {
  const idx = relativePath.lastIndexOf('/');
  return idx >= 0 ? relativePath.slice(0, idx) : '';
}

function compareChildPaths(a: string, b: string, nodes: Map<string, FileNode>): number {
  const na = nodes.get(a);
  const nb = nodes.get(b);
  if (!na || !nb) return a.localeCompare(b, undefined, { sensitivity: 'base' });
  if (na.isDir !== nb.isDir) return na.isDir ? -1 : 1;
  return na.name.localeCompare(nb.name, undefined, { sensitivity: 'base' });
}

function sortChildPaths(children: string[], nodes: Map<string, FileNode>): void {
  children.sort((a, b) => compareChildPaths(a, b, nodes));
}

export function useFileTree(projectPath: () => string | null) {
  const nodes = reactive(new Map<string, FileNode>());
  const rootPaths = shallowRef<string[]>([]);
  const filter = ref('');
  const indexing = ref(false);
  const error = ref<string | null>(null);
  const rootLoaded = ref(false);

  const pendingFsChanges: FsChangePayload[] = [];
  let unlistenFs: UnlistenFn | null = null;
  let loadGeneration = 0;
  let fsListenerGeneration = 0;

  function visibleNodes(): FileNode[] {
    const term = filter.value.trim().toLowerCase();
    if (term) {
      const result: FileNode[] = [];
      for (const node of nodes.values()) {
        if (node.isDir) continue;
        if (node.name.toLowerCase().includes(term)) {
          result.push(node);
        }
      }
      result.sort((a, b) =>
        a.relativePath.localeCompare(b.relativePath, undefined, { sensitivity: 'base' }),
      );
      return result;
    }

    const out: FileNode[] = [];
    function walk(paths: string[]): void {
      for (const p of paths) {
        const node = nodes.get(p);
        if (!node) continue;
        out.push(node);
        if (node.isDir && node.expanded && node.children.length) {
          walk(node.children);
        }
      }
    }
    walk(rootPaths.value);
    return out;
  }

  const flatList = computed<FileNode[]>(() => visibleNodes());
  const matchCount = computed(() =>
    filter.value.trim()
      ? flatList.value.length
      : nodes.size,
  );

  function isParentVisible(parentPath: string): boolean {
    if (parentPath === '') {
      return rootLoaded.value;
    }
    const parent = nodes.get(parentPath);
    return Boolean(parent?.loaded && parent.expanded);
  }

  function removeFromParentChildren(parentPath: string, childPath: string): void {
    if (parentPath === '') {
      rootPaths.value = rootPaths.value.filter((p) => p !== childPath);
      return;
    }
    const parent = nodes.get(parentPath);
    if (!parent) return;
    parent.children = parent.children.filter((p) => p !== childPath);
  }

  function addToParentChildren(parentPath: string, childPath: string): void {
    if (parentPath === '') {
      if (!rootPaths.value.includes(childPath)) {
        rootPaths.value = [...rootPaths.value, childPath];
        sortChildPaths(rootPaths.value, nodes);
      }
      return;
    }
    const parent = nodes.get(parentPath);
    if (!parent) return;
    if (!parent.children.includes(childPath)) {
      parent.children.push(childPath);
      sortChildPaths(parent.children, nodes);
    }
  }

  function removeSubtree(relativePath: string): void {
    const keysToRemove: string[] = [];
    for (const key of nodes.keys()) {
      if (key === relativePath || key.startsWith(`${relativePath}/`)) {
        keysToRemove.push(key);
      }
    }
    for (const key of keysToRemove) {
      nodes.delete(key);
    }
  }

  async function resolveEntry(
    root: string,
    parentPath: string,
    childPath: string,
    payload: FsChangePayload,
  ): Promise<LocalDirEntry | null> {
    try {
      const entries = await listDirEntries(root, parentPath);
      const found = entries.find((entry) => entry.relativePath === childPath);
      if (found) return found;
    } catch {
      // Fallback sur le payload si la lecture du parent échoue.
    }

    const name = childPath.split('/').pop() ?? childPath;
    return {
      name,
      relativePath: childPath,
      isDir: payload.isDir,
      kind: payload.isDir ? 'folder' : 'file',
    };
  }

  async function reconcileCreate(payload: FsChangePayload): Promise<void> {
    const root = projectPath();
    if (!root || nodes.has(payload.path)) return;

    const parentPath = parentRelativePath(payload.path);
    if (!isParentVisible(parentPath)) return;

    const parentNode = parentPath ? nodes.get(parentPath) : null;
    const depth = parentNode ? parentNode.depth + 1 : 0;
    const entry = await resolveEntry(root, parentPath, payload.path, payload);
    if (!entry) return;
    // Abandonner si l'espace a changé ou si le nœud a déjà été créé pendant l'await.
    if (projectPath() !== root || nodes.has(payload.path)) return;
    if (!isParentVisible(parentPath)) return;

    const node = makeNode(entry, depth);
    nodes.set(payload.path, node);
    addToParentChildren(parentPath, payload.path);
  }

  function reconcileDelete(payload: FsChangePayload): void {
    if (!nodes.has(payload.path)) return;

    const parentPath = parentRelativePath(payload.path);
    removeFromParentChildren(parentPath, payload.path);
    removeSubtree(payload.path);
  }

  function reconcileModify(_payload: FsChangePayload): void {
    // No-op : markSessionTouched reste côté agent.
  }

  async function reconcileFsChange(payload: FsChangePayload): Promise<void> {
    switch (payload.kind) {
      case 'create':
        await reconcileCreate(payload);
        break;
      case 'delete':
        reconcileDelete(payload);
        break;
      case 'modify':
        reconcileModify(payload);
        break;
    }
  }

  const flushFsChanges = useDebounceFn(async () => {
    const batch = pendingFsChanges.splice(0);
    const rootAtFlush = projectPath();
    for (const payload of batch) {
      if (projectPath() !== rootAtFlush) return;
      await reconcileFsChange(payload);
    }
  }, 150);

  function queueFsChange(payload: FsChangePayload): void {
    pendingFsChanges.push(payload);
    void flushFsChanges();
  }

  async function bindFsListener(path: string | null): Promise<void> {
    const generation = ++fsListenerGeneration;
    if (unlistenFs) {
      await unlistenFs();
      unlistenFs = null;
    }
    pendingFsChanges.length = 0;

    if (!path) return;

    const listener = await listen<FsChangePayload>('fs-change', (event) => {
      queueFsChange(event.payload);
    });
    if (generation !== fsListenerGeneration) {
      await listener();
      return;
    }
    unlistenFs = listener;
  }

  watch(projectPath, (path) => {
    void bindFsListener(path);
  }, { immediate: true });

  onScopeDispose(() => {
    void unlistenFs?.();
    unlistenFs = null;
    pendingFsChanges.length = 0;
  });

  async function loadDir(relativePath: string): Promise<void> {
    const root = projectPath();
    if (!root) return;
    const capturedRoot = root;
    const parent = relativePath === '' ? null : nodes.get(relativePath);
    if (parent) {
      if (parent.loading || parent.loaded) return;
      parent.loading = true;
    } else {
      indexing.value = true;
    }
    const generation = ++loadGeneration;
    error.value = null;

    const isStale = () =>
      generation !== loadGeneration || projectPath() !== capturedRoot;

    try {
      const entries = await listDirEntries(capturedRoot, relativePath);
      if (isStale()) {
        if (parent) parent.loading = false;
        return;
      }
      const depth = parent ? parent.depth + 1 : 0;
      const childPaths: string[] = [];
      for (const entry of entries) {
        const node = makeNode(entry, depth);
        nodes.set(entry.relativePath, node);
        childPaths.push(entry.relativePath);
      }
      if (parent) {
        parent.children = childPaths;
        parent.loaded = true;
        parent.loading = false;
      } else {
        rootPaths.value = childPaths;
        rootLoaded.value = true;
      }
    } catch (err) {
      if (parent) parent.loading = false;
      if (isStale()) return;
      let detail: string;
      if (err instanceof Error) {
        detail = err.message && err.message.trim()
          ? err.message
          : err.stack || `Error ${err.name || 'Error'} (message vide)`;
      } else if (typeof err === 'string') {
        detail = err;
      } else {
        try {
          detail = JSON.stringify(err);
        } catch {
          detail = String(err);
        }
      }
      error.value = detail && detail.trim() ? detail : 'Indexation impossible';
      console.error('[useFileTree] listDirEntries failed', { root, relativePath, err });
    } finally {
      if (!isStale()) {
        indexing.value = false;
      }
    }
  }

  async function toggle(node: FileNode): Promise<void> {
    if (!node.isDir) return;
    if (!node.loaded) {
      await loadDir(node.relativePath);
    }
    node.expanded = !node.expanded;
  }

  function expandPath(relativePath: string): void {
    if (!relativePath) return;
    const segments = relativePath.split('/').filter(Boolean);
    let current = '';
    for (const segment of segments) {
      const parentPath = current;
      current = current ? `${current}/${segment}` : segment;
      const node = nodes.get(current);
      if (node && node.isDir) {
        node.expanded = true;
      }
    }
  }

  function reset(): void {
    loadGeneration += 1;
    nodes.clear();
    rootPaths.value = [];
    filter.value = '';
    indexing.value = false;
    error.value = null;
    rootLoaded.value = false;
    pendingFsChanges.length = 0;
  }

  function markSessionTouched(relativePath: string, state: 'created' | 'modified'): void {
    const node = nodes.get(relativePath);
    if (node) node.sessionState = state;
  }

  function clearSessionMarks(): void {
    for (const node of nodes.values()) {
      node.sessionState = 'idle';
    }
  }

  return {
    flatList,
    matchCount,
    filter,
    indexing,
    error,
    rowHeight: ROW_HEIGHT,
    loadRoot: () => loadDir(''),
    loadDir,
    toggle,
    expandPath,
    reset,
    markSessionTouched,
    clearSessionMarks,
  };
}
