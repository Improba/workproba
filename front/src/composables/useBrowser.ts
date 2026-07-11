import { computed, ref, type ComputedRef, type Ref } from 'vue';
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
import { BROWSER_PLUGIN_ID, usePlugins } from '@composables/usePlugins';
import { useAppSettings } from '@composables/useAppSettings';

export interface BrowserState {
  active: boolean;
  currentUrl: string;
  title: string;
  screenshot: string | null;
  snapshotYaml: string;
  loading: boolean;
  error: string | null;
}

const currentUrl = ref('');
const title = ref('');
const screenshot = ref<string | null>(null);
const snapshotYaml = ref('');
const active = ref(false);
const loading = ref(false);
const error = ref<string | null>(null);
let pluginDataDir: string | null = null;

function applySnapshotResult(data: Record<string, unknown>): void {
  if (typeof data.url === 'string') currentUrl.value = data.url;
  if (typeof data.title === 'string') title.value = data.title;
  if (typeof data.screenshot_b64 === 'string') {
    screenshot.value = data.screenshot_b64;
  }
  if (typeof data.snapshot_yaml === 'string') {
    snapshotYaml.value = data.snapshot_yaml;
  }
  active.value = true;
}

export interface UseBrowserReturn {
  currentUrl: Ref<string>;
  title: Ref<string>;
  screenshot: Ref<string | null>;
  snapshotYaml: Ref<string>;
  active: Ref<boolean>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  isBrowserPluginActive: ComputedRef<boolean>;
  init: () => Promise<void>;
  navigate: (url: string) => Promise<void>;
  snapshot: () => Promise<void>;
  action: (payload: BrowserActionPayload) => Promise<void>;
  close: () => Promise<void>;
  refresh: () => Promise<void>;
  goBack: () => Promise<void>;
  goForward: () => Promise<void>;
  applyToolResult: (toolName: string, result: unknown) => void;
}

export function useBrowser(): UseBrowserReturn {
  const { isBrowserPluginActive, getPluginDataDir } = usePlugins();
  const { settingsLocked, permissionsNetwork, locale } = useAppSettings();

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
    try {
      const status = await browserStatus(dir);
      active.value = status.active;
      currentUrl.value = status.url ?? '';
      title.value = status.title ?? '';
      if (status.active) {
        await snapshot();
      }
    } catch {
      /* défensif : back peut être indisponible */
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

    loading.value = true;
    error.value = null;
    try {
      const result = await browserNavigate(dir, trimmed, securityContext());
      applySnapshotResult(result as unknown as Record<string, unknown>);
    } catch (err) {
      error.value = mapBrowserError(err);
    } finally {
      loading.value = false;
    }
  }

  async function snapshot(): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) return;

    loading.value = true;
    error.value = null;
    try {
      const result = await browserSnapshot(dir, securityContext());
      applySnapshotResult(result as unknown as Record<string, unknown>);
    } catch (err) {
      error.value = mapBrowserError(err);
    } finally {
      loading.value = false;
    }
  }

  async function action(payload: BrowserActionPayload): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) return;

    loading.value = true;
    error.value = null;
    try {
      const result = await browserAction(dir, payload, securityContext());
      applySnapshotResult(result as unknown as Record<string, unknown>);
    } catch (err) {
      error.value = mapBrowserError(err);
    } finally {
      loading.value = false;
    }
  }

  async function close(): Promise<void> {
    const dir = await ensureDataDir();
    if (!dir) return;

    try {
      await browserClose(dir);
      active.value = false;
      screenshot.value = null;
      snapshotYaml.value = '';
      currentUrl.value = '';
      title.value = '';
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

  function applyToolResult(toolName: string, result: unknown): void {
    if (!result || typeof result !== 'object') return;
    const browserTools = new Set(['browser_navigate', 'browser_click', 'browser_extract']);
    if (!browserTools.has(toolName)) return;
    applySnapshotResult(result as Record<string, unknown>);
    error.value = null;
  }

  return {
    currentUrl,
    title,
    screenshot,
    snapshotYaml,
    active,
    loading,
    error,
    isBrowserPluginActive,
    init,
    navigate,
    snapshot,
    action,
    close,
    refresh,
    goBack,
    goForward,
    applyToolResult,
  };
}

export { BROWSER_PLUGIN_ID };
