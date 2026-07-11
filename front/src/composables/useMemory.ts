import { ref, type Ref } from 'vue';
import {
  addMemoryItem,
  fetchMemoryItems,
  forgetAllMemory,
  forgetMemoryItem,
  searchMemory,
  type ForgetMemoryScope,
  type MemoryItem,
  type MemoryScope,
  type MemorySearchResult,
  type MemorySearchScope,
} from '@services/aiSidecar';

export interface UseMemoryReturn {
  memories: Ref<MemoryItem[]>;
  searchResults: Ref<MemorySearchResult[]>;
  loading: Ref<boolean>;
  searching: Ref<boolean>;
  loadError: Ref<string | null>;
  refresh: (workspaceDataDir: string | null, scope?: MemoryScope) => Promise<void>;
  searchMemory: (
    workspaceDataDir: string | null,
    query: string,
    scope?: MemorySearchScope,
  ) => Promise<void>;
  addMemory: (
    workspaceDataDir: string | null,
    content: string,
    scope?: MemoryScope,
    tags?: string[],
  ) => Promise<MemoryItem | null>;
  forgetMemory: (
    workspaceDataDir: string | null,
    memoryId: string,
    scope?: MemoryScope,
  ) => Promise<boolean>;
  forgetAll: (
    workspaceDataDir: string | null,
    scope?: ForgetMemoryScope,
    memoryScope?: MemoryScope,
  ) => Promise<boolean>;
}

export function useMemory(): UseMemoryReturn {
  const memories = ref<MemoryItem[]>([]);
  const searchResults = ref<MemorySearchResult[]>([]);
  const loading = ref(false);
  const searching = ref(false);
  const loadError = ref<string | null>(null);

  async function refresh(workspaceDataDir: string | null, scope: MemoryScope = 'project'): Promise<void> {
    if (!workspaceDataDir) {
      memories.value = [];
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      memories.value = await fetchMemoryItems(workspaceDataDir, scope);
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : 'memory_load_failed';
      memories.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function searchMemoryQuery(
    workspaceDataDir: string | null,
    query: string,
    scope: MemorySearchScope = 'project',
  ): Promise<void> {
    if (!workspaceDataDir || !query.trim()) {
      searchResults.value = [];
      return;
    }
    searching.value = true;
    try {
      searchResults.value = await searchMemory(workspaceDataDir, query.trim(), scope);
    } catch {
      searchResults.value = [];
    } finally {
      searching.value = false;
    }
  }

  async function addMemory(
    workspaceDataDir: string | null,
    content: string,
    scope: MemoryScope = 'project',
    tags: string[] = [],
  ): Promise<MemoryItem | null> {
    if (!workspaceDataDir || !content.trim()) return null;
    const entry = await addMemoryItem(workspaceDataDir, content.trim(), scope, tags);
    if (entry) {
      memories.value = [entry, ...memories.value];
    }
    return entry;
  }

  async function forgetMemory(
    workspaceDataDir: string | null,
    memoryId: string,
    scope: MemoryScope = 'project',
  ): Promise<boolean> {
    if (!workspaceDataDir) return false;
    const ok = await forgetMemoryItem(workspaceDataDir, memoryId, scope);
    if (ok) {
      memories.value = memories.value.filter((m) => m.id !== memoryId);
      searchResults.value = searchResults.value.filter(
        (m) => (m.memory_id ?? m.id) !== memoryId,
      );
    }
    return ok;
  }

  async function forgetAll(
    workspaceDataDir: string | null,
    scope: ForgetMemoryScope = 'all',
    memoryScope: MemoryScope = 'project',
  ): Promise<boolean> {
    if (!workspaceDataDir) return false;
    const ok = await forgetAllMemory(workspaceDataDir, scope, memoryScope);
    if (ok) {
      memories.value = [];
      searchResults.value = [];
    }
    return ok;
  }

  return {
    memories,
    searchResults,
    loading,
    searching,
    loadError,
    refresh,
    searchMemory: searchMemoryQuery,
    addMemory,
    forgetMemory,
    forgetAll,
  };
}
