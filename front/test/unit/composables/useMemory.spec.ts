import { describe, expect, it, vi, beforeEach } from 'vitest';

const fetchMemoryItems = vi.fn();
const searchMemory = vi.fn();
const addMemoryItem = vi.fn();
const forgetMemoryItem = vi.fn();
const forgetAllMemory = vi.fn();

vi.mock('@services/aiSidecar', () => ({
  fetchMemoryItems,
  searchMemory,
  addMemoryItem,
  forgetMemoryItem,
  forgetAllMemory,
}));

describe('useMemory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('refresh charge les souvenirs du scope demandé', async () => {
    fetchMemoryItems.mockResolvedValue([
      { id: 'mem_1', content: 'Budget RH', source: 'manual', created_at: '', tags: [] },
    ]);

    const { useMemory } = await import('@composables/useMemory');
    const { refresh, memories, loading } = useMemory();

    expect(loading.value).toBe(false);
    const pending = refresh('/data/ws', 'project');
    expect(loading.value).toBe(true);
    await pending;

    expect(fetchMemoryItems).toHaveBeenCalledWith('/data/ws', 'project');
    expect(memories.value).toHaveLength(1);
    expect(loading.value).toBe(false);
  });

  it('addMemory préfixe la liste locale après succès API', async () => {
    const entry = {
      id: 'mem_new',
      content: 'Nouveau fait',
      source: 'manual',
      created_at: '2026-07-14T12:00:00Z',
      tags: [],
    };
    addMemoryItem.mockResolvedValue(entry);

    const { useMemory } = await import('@composables/useMemory');
    const { addMemory, memories } = useMemory();

    const result = await addMemory('/data/ws', 'Nouveau fait', 'project');
    expect(result).toEqual(entry);
    expect(memories.value[0]).toEqual(entry);
  });

  it('forgetMemory retire l\'entrée locale après succès API', async () => {
    fetchMemoryItems.mockResolvedValue([
      { id: 'mem_1', content: 'A', source: 'manual', created_at: '', tags: [] },
      { id: 'mem_2', content: 'B', source: 'manual', created_at: '', tags: [] },
    ]);
    forgetMemoryItem.mockResolvedValue(true);

    const { useMemory } = await import('@composables/useMemory');
    const { refresh, forgetMemory, memories } = useMemory();
    await refresh('/data/ws', 'project');

    const ok = await forgetMemory('/data/ws', 'mem_1', 'project');
    expect(ok).toBe(true);
    expect(memories.value.map((item) => item.id)).toEqual(['mem_2']);
  });

  it('forgetAll utilise memories par défaut et vide l\'état local', async () => {
    forgetAllMemory.mockResolvedValue(true);

    const { useMemory } = await import('@composables/useMemory');
    const { forgetAll, memories, searchResults } = useMemory();
    memories.value = [
      { id: 'mem_1', content: 'A', source: 'manual', created_at: '', tags: [] },
    ];
    searchResults.value = [
      {
        id: 'mem_1',
        content: 'A',
        source: 'manual',
        kind: 'memory',
      },
    ];

    const ok = await forgetAll('/data/ws');
    expect(ok).toBe(true);
    expect(forgetAllMemory).toHaveBeenCalledWith('/data/ws', 'memories', 'project');
    expect(memories.value).toEqual([]);
    expect(searchResults.value).toEqual([]);
  });

  it('forgetAll propage memory_scope user au client API', async () => {
    forgetAllMemory.mockResolvedValue(true);

    const { useMemory } = await import('@composables/useMemory');
    const { forgetAll } = useMemory();

    await forgetAll('/data/ws', 'memories', 'user');
    expect(forgetAllMemory).toHaveBeenCalledWith('/data/ws', 'memories', 'user');
  });

  it('forgetAll retourne false sans appeler l\'API si workspace absent', async () => {
    const { useMemory } = await import('@composables/useMemory');
    const { forgetAll } = useMemory();

    const ok = await forgetAll(null);
    expect(ok).toBe(false);
    expect(forgetAllMemory).not.toHaveBeenCalled();
  });
});
