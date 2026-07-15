import { computed, ref, watch, type ComputedRef, type Ref } from 'vue';
import {
  browserAction,
  browserClose,
  browserNavigate,
  browserSnapshot,
  browserStatus,
  buildSidecarSecurityContext,
  isBrowserLockedError,
  type BrowserActionPayload,
} from '@services/aiSidecar';
import {
  buildBrowserAiActionOverlay,
  type BrowserAiActionOverlay,
} from '@utils/browserActionLabel';
import {
  parseBrowserHighlight,
  type BrowserHighlightState,
} from '@utils/browserHighlight';
import { isBrowserAgentTool } from '@utils/browserTools';
import { BROWSER_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useAppSettings } from '@composables/useAppSettings';

const LIVE_REFRESH_MS = 1200;
const HIGHLIGHT_FADE_MS = 2500;

export type BrowserLoadingReason = 'init' | 'navigate' | 'snapshot' | 'action';

export interface BrowserState {
  active: boolean;
  currentUrl: string;
  title: string;
  screenshot: string | null;
  snapshotYaml: string;
  loading: boolean;
  loadingReason: BrowserLoadingReason | null;
  loadingStartedAt: number | null;
  error: string | null;
  pilotagePaused: boolean;
  lastAiAction: BrowserAiActionOverlay | null;
  highlight: BrowserHighlightState | null;
  agentTurnActive: boolean;
}

const currentUrl = ref('');
const title = ref('');
const screenshot = ref<string | null>(null);
const snapshotYaml = ref('');
const active = ref(false);
const loading = ref(false);
const loadingReason = ref<BrowserLoadingReason | null>(null);
const loadingStartedAt = ref<number | null>(null);
const error = ref<string | null>(null);
const pilotagePaused = ref(false);
const lastAiAction = ref<BrowserAiActionOverlay | null>(null);
const highlight = ref<BrowserHighlightState | null>(null);
const agentTurnActive = ref(false);
let pluginDataDir: string | null = null;
let liveRefreshTimer: ReturnType<typeof setInterval> | null = null;
let highlightFadeTimer: ReturnType<typeof setTimeout> | null = null;
let silentSnapshotFn: ((options?: SnapshotOptions) => Promise<void>) | null = null;
let browserWatchesRegistered = false;

export interface SnapshotOptions {
  silent?: boolean;
}

function clearHighlightFadeTimer(): void {
  if (highlightFadeTimer) {
    clearTimeout(highlightFadeTimer);
    highlightFadeTimer = null;
  }
}

function scheduleHighlightFade(): void {
  clearHighlightFadeTimer();
  highlightFadeTimer = setTimeout(() => {
    highlight.value = null;
    highlightFadeTimer = null;
  }, HIGHLIGHT_FADE_MS);
}

function applySnapshotResult(
  data: Record<string, unknown>,
  options: { markActive?: boolean } = {},
): void {
  if (typeof data.url === 'string') currentUrl.value = data.url;
  if (typeof data.title === 'string') title.value = data.title;
  if (typeof data.screenshot_b64 === 'string' && data.screenshot_b64) {
    screenshot.value = data.screenshot_b64;
  }
  if (typeof data.snapshot_yaml === 'string') {
    snapshotYaml.value = data.snapshot_yaml;
  }
  if (options.markActive !== false) {
    active.value = true;
  }

  const parsedHighlight = parseBrowserHighlight(data);
  if (parsedHighlight) {
    highlight.value = parsedHighlight;
    scheduleHighlightFade();
  }
}

function stopLiveRefresh(): void {
  if (liveRefreshTimer) {
    clearInterval(liveRefreshTimer);
    liveRefreshTimer = null;
  }
}

function syncLiveRefresh(): void {
  stopLiveRefresh();
  if (!agentTurnActive.value || pilotagePaused.value || !active.value) return;
  liveRefreshTimer = setInterval(() => {
    void silentSnapshotFn?.({ silent: true });
  }, LIVE_REFRESH_MS);
}

function beginLoading(reason: BrowserLoadingReason): void {
  loading.value = true;
  loadingReason.value = reason;
  loadingStartedAt.value = Date.now();
}

function endLoading(): void {
  loading.value = false;
  loadingReason.value = null;
  loadingStartedAt.value = null;
}

function registerBrowserWatches(isBrowserPluginActive: Ref<boolean>): void {
  if (browserWatchesRegistered) return;
  watch(isBrowserPluginActive, (pluginActive) => {
    if (!pluginActive) {
      pluginDataDir = null;
    }
  });
  watch(pilotagePaused, syncLiveRefresh);
  watch(active, syncLiveRefresh);
  browserWatchesRegistered = true;
}

export interface UseBrowserReturn {
  currentUrl: Ref<string>;
  title: Ref<string>;
  screenshot: Ref<string | null>;
  snapshotYaml: Ref<string>;
  active: Ref<boolean>;
  loading: Ref<boolean>;
  loadingReason: Ref<BrowserLoadingReason | null>;
  loadingStartedAt: Ref<number | null>;
  error: Ref<string | null>;
  pilotagePaused: Ref<boolean>;
  lastAiAction: Ref<BrowserAiActionOverlay | null>;
  highlight: Ref<BrowserHighlightState | null>;
  agentTurnActive: Ref<boolean>;
  isBrowserPluginActive: ComputedRef<boolean>;
  init: () => Promise<void>;
  navigate: (url: string) => Promise<void>;
  snapshot: (options?: SnapshotOptions) => Promise<void>;
  action: (payload: BrowserActionPayload) => Promise<void>;
  close: () => Promise<void>;
  refresh: () => Promise<void>;
  goBack: () => Promise<void>;
  goForward: () => Promise<void>;
  pausePilotage: () => void;
  resumePilotage: () => void;
  setAgentTurnActive: (active: boolean) => void;
  applyToolResult: (toolName: string, result: unknown, isError?: boolean) => void;
}

export function useBrowser(): UseBrowserReturn {
  const { isBrowserPluginActive, getPluginDataDir } = usePlugins();
  const { settingsLocked, permissionsNetwork, locale } = useAppSettings();

  registerBrowserWatches(isBrowserPluginActive);

  function securityContext() {
    return buildSidecarSecurityContext(
      settingsLocked.value,
      permissionsNetwork.value,
      locale.value,
    );
  }

  function mapBrowserError(err: unknown): string {
    const message = err instanceof Error ? err.message : 'browser_action_failed';
    if (isBrowserLockedError(message)) return 'browser_locked';
    return message;
  }

  async function ensureDataDir(): Promise<string | null> {
    if (pluginDataDir) return pluginDataDir;
    if (!isBrowserPluginActive.value) return null;
    try {
      pluginDataDir = await getPluginDataDir(BROWSER_PLUGIN_ID);
      return pluginDataDir;
    } catch {
      return null;
    }
  }

  async function init(): Promise<void> {
    if (!isBrowserPluginActive.value) return;
    const dir = await ensureDataDir();
    if (!dir) return;
    beginLoading('init');
    error.value = null;
    try {
      const status = await browserStatus(dir);
      active.value = status.active;
      currentUrl.value = status.url ?? '';
      title.value = status.title ?? '';
      if (status.active) {
        await snapshot({ silent: true });
      }
    } catch {
      /* défensif : back peut être indisponible */
    } finally {
      endLoading();
    }
  }

  async function navigate(url: string): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) {
      error.value = 'browser_unavailable';
      return;
    }
    const trimmed = url.trim();
    if (!trimmed) return;

    beginLoading('navigate');
    error.value = null;
    lastAiAction.value = null;
    highlight.value = null;
    clearHighlightFadeTimer();
    try {
      const result = await browserNavigate(dir, trimmed, securityContext());
      applySnapshotResult(result as unknown as Record<string, unknown>);
    } catch (err) {
      error.value = mapBrowserError(err);
    } finally {
      endLoading();
    }
  }

  async function snapshot(options: SnapshotOptions = {}): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) return;
    if (options.silent && !active.value) return;

    if (!options.silent) {
      beginLoading('snapshot');
      error.value = null;
    }
    try {
      const result = await browserSnapshot(dir, securityContext());
      applySnapshotResult(result as unknown as Record<string, unknown>, {
        markActive: !options.silent,
      });
    } catch (err) {
      if (!options.silent) {
        error.value = mapBrowserError(err);
      }
    } finally {
      if (!options.silent) {
        endLoading();
      }
    }
  }

  async function action(payload: BrowserActionPayload): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) return;

    beginLoading('action');
    error.value = null;
    lastAiAction.value = null;
    highlight.value = null;
    clearHighlightFadeTimer();
    try {
      const result = await browserAction(dir, payload, securityContext());
      applySnapshotResult(result as unknown as Record<string, unknown>);
    } catch (err) {
      error.value = mapBrowserError(err);
    } finally {
      endLoading();
    }
  }

  async function close(): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) return;

    stopLiveRefresh();
    try {
      await browserClose(dir);
      active.value = false;
      screenshot.value = null;
      snapshotYaml.value = '';
      currentUrl.value = '';
      title.value = '';
      lastAiAction.value = null;
      highlight.value = null;
      clearHighlightFadeTimer();
    } catch {
      /* défensif */
    }
  }

  async function refresh(): Promise<void> {
    if (currentUrl.value) {
      await navigate(currentUrl.value);
    } else {
      await snapshot();
    }
  }

  async function goBack(): Promise<void> {
    await action({ action: 'back' });
  }

  async function goForward(): Promise<void> {
    await action({ action: 'forward' });
  }

  function pausePilotage(): void {
    pilotagePaused.value = true;
    stopLiveRefresh();
  }

  function resumePilotage(): void {
    pilotagePaused.value = false;
    syncLiveRefresh();
  }

  function setAgentTurnActive(next: boolean): void {
    agentTurnActive.value = next;
    syncLiveRefresh();
  }

  function applyToolResult(toolName: string, result: unknown, isError = false): void {
    if (isError) return;
    if (!result || typeof result !== 'object') return;
    if (!isBrowserAgentTool(toolName)) return;
    stopLiveRefresh();
    const payload = result as Record<string, unknown>;
    applySnapshotResult(payload);
    if (typeof payload.screenshot_b64 !== 'string' || !payload.screenshot_b64) {
      void snapshot({ silent: true });
    }
    error.value = null;
    lastAiAction.value = buildBrowserAiActionOverlay(toolName, payload);
    syncLiveRefresh();
  }

  silentSnapshotFn = snapshot;

  return {
    currentUrl,
    title,
    screenshot,
    snapshotYaml,
    active,
    loading,
    loadingReason,
    loadingStartedAt,
    error,
    pilotagePaused,
    lastAiAction,
    highlight,
    agentTurnActive,
    isBrowserPluginActive,
    init,
    navigate,
    snapshot,
    action,
    close,
    refresh,
    goBack,
    goForward,
    pausePilotage,
    resumePilotage,
    setAgentTurnActive,
    applyToolResult,
  };
}

export { BROWSER_PLUGIN_ID };
