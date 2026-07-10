import { computed, ref, watch, type Ref } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';

import { useProject } from '@composables/useProject';
import { useAppSettings, buildActiveLlmConfigs, type LlmConfigPayload } from '@composables/useAppSettings';
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
  embeddingConfig: LlmConfigPayload | null;
  paths?: string[] | null;
}): Promise<void> {
  try {
    const result = await indexWorkspace({
      projectPath: opts.projectPath,
      workspaceDataDir: opts.workspaceDataDir,
      embeddingConfig: opts.embeddingConfig,
      paths: opts.paths ?? null,
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
  const { activePath, activeDataDir } = useProject();
  const projectPath = activePath.value;
  if (!projectPath) return;

  const embedding = buildActiveLlmConfigs().embedding;
  if (!embedding) {
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
    embeddingConfig: embedding,
  });
  currentJob = null;
  drainPending();
}

async function triggerPaths(paths: string[]): Promise<void> {
  const { activePath, activeDataDir } = useProject();
  const projectPath = activePath.value;
  if (!projectPath || paths.length === 0) return;

  const embedding = buildActiveLlmConfigs().embedding;
  if (!embedding) {
    status.value = 'disabled';
    return;
  }

  // Une passe full en cours couvre déjà ces chemins a priori : on ne lance
  // pas de re-index ciblé en parallèle. Mais la passe full prend un snapshot
  // des candidats au démarrage de sa collecte ; un fichier créé pendant la
  // passe ne sera PAS couvert. On replanifie donc les chemins pour qu'ils
  // soient traités par `drainPending` à la fin de la passe full, au lieu de
  // les perdre (flushPaths a déjà vidé pendingPaths avant cet appel).
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
    embeddingConfig: embedding,
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

  const { activeWorkspaceId } = useProject();
  const { activeEmbeddingProvider } = useAppSettings();

  // (Re)indexe quand le workspace actif change ou qu'un provider d'embedding
  // devient disponible / change.
  const triggerKey = computed(
    () => `${activeWorkspaceId.value ?? ''}::${activeEmbeddingProvider.value?.id ?? ''}`,
  );
  watch(
    triggerKey,
    (next, prev) => {
      if (!next) {
        status.value = 'idle';
        return;
      }
      // Évite le double déclenchement quand workspace et provider se résolvent
      // quasi simultanément : on ne déclenche que si la clé a réellement changé.
      if (next === prev) return;
      void triggerFull();
    },
    { immediate: true },
  );

  // Re-index ciblé sur les évènements FS (create / modify de fichiers).
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
