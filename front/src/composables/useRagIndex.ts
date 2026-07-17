import { computed, ref, watch, type Ref } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';

import { useSpace } from '@composables/useSpace';
import { buildActiveProviderSet, useAppSettings } from '@composables/useAppSettings';
import { CLOUD_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useCloud } from '@composables/useCloud';
import { ensureProviderSetEmbeddingsReady } from '@utils/providerSetNotify';
import {
  usesDeviceBearerAuth,
} from '@utils/providerSetValidation';
import {
  indexWorkspace,
  type RagStatus,
  type WorkspaceIndexReport,
} from '@services/aiSidecar';

const DEBOUNCE_MS = 800;

const status = ref<RagStatus>('idle');
const report = ref<WorkspaceIndexReport | null>(null);
const error = ref<string | null>(null);
const lastRunAt = ref<number | null>(null);

let started = false;
let unlistenFs: UnlistenFn | null = null;
let currentJob: 'full' | 'paths' | null = null;
let pendingFull = false;
const pendingPaths = new Set<string>();

const flushPaths = useDebounceFn(async () => {
  if (pendingPaths.size === 0) return;
  const paths = Array.from(pendingPaths);
  pendingPaths.clear();
  await triggerPaths(paths);
}, DEBOUNCE_MS);

function queuePath(path: string): void {
  pendingPaths.add(path);
  void flushPaths();
}

async function runIndex(opts: {
  projectPath: string;
  workspaceDataDir: string | null;
  paths?: string[] | null;
}): Promise<void> {
  const { getPluginDataDir } = usePlugins();
  const { providerReadiness, init: initCloud } = useCloud();
  const providerSet = buildActiveProviderSet(null, null);
  if (!providerSet?.embeddings) {
    status.value = 'disabled';
    return;
  }
  if (usesDeviceBearerAuth(providerSet) && !providerReadiness.value) {
    await initCloud();
  }
  const cloudCtx = usesDeviceBearerAuth(providerSet)
    ? providerReadiness.value
    : null;
  if (!ensureProviderSetEmbeddingsReady(providerSet, cloudCtx)) {
    status.value = 'disabled';
    error.value = 'api_key_missing';
    return;
  }

  try {
    const cloudPluginDataDir = await getPluginDataDir(CLOUD_PLUGIN_ID);
    const result = await indexWorkspace({
      projectPath: opts.projectPath,
      workspaceDataDir: opts.workspaceDataDir,
      providerSet,
      paths: opts.paths ?? null,
      cloudPluginDataDir,
    });
    report.value = result;
    error.value = null;
    status.value = result.enabled ? 'done' : 'disabled';
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Indexation échouée';
    status.value = 'error';
  } finally {
    lastRunAt.value = Date.now();
  }
}

async function triggerFull(): Promise<void> {
  const { activePath, activeDataDir } = useSpace();
  const projectPath = activePath.value;
  if (!projectPath) return;

  const providerSet = buildActiveProviderSet(null, null);
  if (!providerSet?.embeddings) {
    status.value = 'disabled';
    return;
  }

  if (currentJob === 'full') return;
  if (currentJob === 'paths') {
    pendingFull = true;
    return;
  }

  currentJob = 'full';
  status.value = 'indexing';
  await runIndex({
    projectPath,
    workspaceDataDir: activeDataDir.value,
  });
  currentJob = null;
  drainPending();
}

async function triggerPaths(paths: string[]): Promise<void> {
  const { activePath, activeDataDir } = useSpace();
  const projectPath = activePath.value;
  if (!projectPath || paths.length === 0) return;

  const providerSet = buildActiveProviderSet(null, null);
  if (!providerSet?.embeddings) {
    status.value = 'disabled';
    return;
  }

  if (currentJob === 'full') {
    for (const p of paths) pendingPaths.add(p);
    return;
  }
  if (currentJob === 'paths') {
    for (const p of paths) pendingPaths.add(p);
    return;
  }

  currentJob = 'paths';
  status.value = 'indexing';
  await runIndex({
    projectPath,
    workspaceDataDir: activeDataDir.value,
    paths,
  });
  currentJob = null;
  drainPending();
}

function drainPending(): void {
  if (pendingFull) {
    pendingFull = false;
    void triggerFull();
    return;
  }
  if (pendingPaths.size > 0) {
    const paths = Array.from(pendingPaths);
    pendingPaths.clear();
    void triggerPaths(paths);
  }
}

function ensureStarted(): void {
  if (started) return;
  started = true;

  const { activeSpaceId } = useSpace();
  const { activeSet } = useAppSettings();

  const triggerKey = computed(() => {
    const ws = activeSpaceId.value ?? '';
    const set = activeSet.value;
    if (!set?.embeddings) return `${ws}::none`;
    const embed = set.embeddings;
    return `${ws}::${set.id}::${embed.provider}::${embed.model}`;
  });

  watch(
    triggerKey,
    (next, prev) => {
      if (!next || next.endsWith('::none')) {
        status.value = 'idle';
        return;
      }
      if (next === prev) return;
      void triggerFull();
    },
    { immediate: true },
  );

  void (async () => {
    try {
      unlistenFs = await listen<{ kind: string; path: string; isDir: boolean }>(
        'fs-change',
        (event) => {
          const payload = event.payload;
          if (payload.isDir) return;
          if (payload.kind === 'create' || payload.kind === 'modify') {
            queuePath(payload.path);
          }
        },
      );
    } catch {
      // Tauri indisponible (tests, web) : on ignore silencieusement.
    }
  })();
}

export interface UseRagIndexReturn {
  status: Ref<RagStatus>;
  report: Ref<WorkspaceIndexReport | null>;
  error: Ref<string | null>;
  lastRunAt: Ref<number | null>;
  triggerFull: () => Promise<void>;
}

export function useRagIndex(): UseRagIndexReturn {
  ensureStarted();
  return { status, report, error, lastRunAt, triggerFull };
}
