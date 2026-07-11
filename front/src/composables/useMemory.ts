import { ref, type Ref } from 'vue';
import {
  fetchMemoryItems,
  forgetAllMemory,
  forgetMemoryItem,
  searchMemory,
  type ForgetMemoryScope,
  type MemoryItem,
  type MemorySearchResult,
} from '@services/aiSidecar';

const memories = ref<MemoryItem[]>([]);
const searchResults = ref<MemorySearchResult[]>([]);
const loading = ref(false);
const searching = ref(false);
const loadError = ref<string | null>(null);

export interface UseMemoryReturn {
  memories: Ref<MemoryItem[]>;
  searchResults: Ref<MemorySearchResult[]>;
  loading: Ref<boolean>;
  searching: Ref<boolean>;
  loadError: Ref<string | null>;
  refresh: (workspaceDataDir: string) => Promise<void>;
  searchMemory: (workspaceDataDir: string, query: string) => Promise<void>;
  forgetMemory: (workspaceDataDir: string, memoryId: string) => Promise<boolean>;
  forgetAll: (workspaceDataDir: string, scope?: ForgetMemoryScope) => Promise<boolean>;
}

export function useMemory(): UseMemoryReturn {
  async function refresh(workspaceDataDir: string): Promise<void> {
    if (!workspaceDataDir) {
      memories.value = [];
      return;
    }
    loading.value = true;
    loadError.value = null;
    try {
      memories.value = await fetchMemoryItems(workspaceDataDir);
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : 'memory_load_failed';
      memories.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function searchMemoryQuery(
    workspaceDataDir: string,
    query: string,
  ): Promise<void> {
    if (!workspaceDataDir || !query.trim()) {
      searchResults.value = [];
      return;
    }
    searching.value = true;
    try {
      searchResults.value = await searchMemory(workspaceDataDir, query.trim());
    } catch {
      searchResults.value = [];
    } finally {
      searching.value = false;
    }
  }

  async function forgetMemory(
    workspaceDataDir: string,
    memoryId: string,
  ): Promise<boolean> {
    const ok = await forgetMemoryItem(workspaceDataDir, memoryId);
    if (ok) {
      memories.value = memories.value.filter((m) => m.id !== memoryId);
      searchResults.value = searchResults.value.filter((m) => m.id !== memoryId);
    }
    return ok;
  }

  async function forgetAll(
    workspaceDataDir: string,
    scope: ForgetMemoryScope = 'all',
  ): Promise<boolean> {
    const ok = await forgetAllMemory(workspaceDataDir, scope);
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
    forgetMemory,
    forgetAll,
  };
}
