import { defineComponent, ref } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const listDirEntries = vi.fn();
const listen = vi.fn();

vi.mock('@composables/useDesktop', () => ({
  listDirEntries: (...args: unknown[]) => listDirEntries(...args),
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: (...args: unknown[]) => listen(...args),
}));

import { useFileTree } from '@composables/useFileTree';

function mountTree(initialPath: string | null = '/proj-a') {
  const projectPath = ref<string | null>(initialPath);
  let api!: ReturnType<typeof useFileTree>;

  const wrapper = mount(
    defineComponent({
      setup() {
        api = useFileTree(() => projectPath.value);
        return {};
      },
      template: '<div />',
    }),
  );

  return { api, projectPath, unmount: () => wrapper.unmount() };
}

describe('useFileTree', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listen.mockResolvedValue(vi.fn());
    listDirEntries.mockImplementation(async (_root: string, dir: string) => {
      if (dir === '') {
        return [
          {
            name: 'readme.md',
            relativePath: 'readme.md',
            isDir: false,
            kind: 'file',
          },
        ];
      }
      return [];
    });
  });

  it('ignore les résultats loadDir obsolètes après reset', async () => {
    let resolveFirst: ((value: unknown) => void) | null = null;
    listDirEntries.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
    );

    const { api, projectPath, unmount } = mountTree('/proj-a');
    const loadPromise = api.loadRoot();

    api.reset();
    projectPath.value = '/proj-b';
    listDirEntries.mockResolvedValueOnce([
      {
        name: 'other.md',
        relativePath: 'other.md',
        isDir: false,
        kind: 'file',
      },
    ]);
    await api.loadRoot();

    resolveFirst?.([
      {
        name: 'stale.md',
        relativePath: 'stale.md',
        isDir: false,
        kind: 'file',
      },
    ]);
    await loadPromise;

    expect(api.flatList.value.map((n) => n.relativePath)).toEqual(['other.md']);
    unmount();
  });

  it('n\'applique pas error/indexing d\'un loadDir obsolète', async () => {
    let rejectFirst: ((reason?: unknown) => void) | null = null;
    listDirEntries.mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          rejectFirst = reject;
        }),
    );

    const { api, projectPath, unmount } = mountTree('/proj-a');
    const loadPromise = api.loadRoot();
    expect(api.indexing.value).toBe(true);

    api.reset();
    projectPath.value = '/proj-b';
    listDirEntries.mockResolvedValueOnce([
      {
        name: 'fresh.md',
        relativePath: 'fresh.md',
        isDir: false,
        kind: 'file',
      },
    ]);
    const second = api.loadRoot();
    expect(api.indexing.value).toBe(true);

    rejectFirst?.(new Error('ancien projet'));
    await loadPromise;
    await second;

    expect(api.error.value).toBeNull();
    expect(api.indexing.value).toBe(false);
    expect(api.flatList.value.map((n) => n.relativePath)).toEqual(['fresh.md']);
    unmount();
  });

  it('ignore reconcileCreate obsolète après changement d\'espace', async () => {
    vi.useFakeTimers();
    let resolveEntries: ((value: unknown) => void) | null = null;
    let listener: ((event: { payload: unknown }) => void) | null = null;

    listen.mockImplementation(async (_event: string, cb: (event: { payload: unknown }) => void) => {
      listener = cb;
      return vi.fn();
    });

    const { api, projectPath, unmount } = mountTree('/proj-a');
    await api.loadRoot();
    await Promise.resolve();

    listDirEntries.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveEntries = resolve;
        }),
    );

    listener?.({
      payload: {
        path: 'ghost.md',
        kind: 'create',
        isDir: false,
      },
    });
    await vi.advanceTimersByTimeAsync(150);

    api.reset();
    projectPath.value = '/proj-b';
    listDirEntries.mockResolvedValueOnce([
      {
        name: 'fresh.md',
        relativePath: 'fresh.md',
        isDir: false,
        kind: 'file',
      },
    ]);
    await api.loadRoot();

    resolveEntries?.([
      {
        name: 'ghost.md',
        relativePath: 'ghost.md',
        isDir: false,
        kind: 'file',
      },
    ]);
    await Promise.resolve();
    await Promise.resolve();

    expect(api.flatList.value.map((n) => n.relativePath)).toEqual(['fresh.md']);
    expect(api.flatList.value.some((n) => n.relativePath === 'ghost.md')).toBe(false);
    vi.useRealTimers();
    unmount();
  });

  it('ignore bindFsListener si un bind plus récent a démarré', async () => {
    let resolveFirstListen: ((value: UnlistenFn) => void) | null = null;
    const staleUnlisten = vi.fn();
    const freshUnlisten = vi.fn();

    listen
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirstListen = resolve;
          }),
      )
      .mockResolvedValueOnce(freshUnlisten);

    const { projectPath, unmount } = mountTree('/proj-a');
    await Promise.resolve();

    projectPath.value = '/proj-b';
    await Promise.resolve();

    resolveFirstListen?.(staleUnlisten);
    await Promise.resolve();

    expect(staleUnlisten).toHaveBeenCalled();
    expect(listen).toHaveBeenCalledTimes(2);
    unmount();
  });
});

type UnlistenFn = () => void | Promise<void>;
