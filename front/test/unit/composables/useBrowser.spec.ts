import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import {
  BROWSER_AGENT_TOOL_NAMES,
  isBrowserAgentTool,
} from '@utils/browserTools';

describe('browserTools', () => {
  it('liste les 8 outils agent browser', () => {
    expect(BROWSER_AGENT_TOOL_NAMES).toHaveLength(8);
    expect(BROWSER_AGENT_TOOL_NAMES).toContain('browser_type');
    expect(BROWSER_AGENT_TOOL_NAMES).toContain('browser_scroll');
  });

  it('isBrowserAgentTool reconnaît les outils browser', () => {
    expect(isBrowserAgentTool('browser_navigate')).toBe(true);
    expect(isBrowserAgentTool('browser_forward')).toBe(true);
    expect(isBrowserAgentTool('list_files')).toBe(false);
  });
});

const browserMocks = vi.hoisted(() => ({
  browserNavigate: vi.fn(),
  browserAction: vi.fn(),
  browserSnapshot: vi.fn(),
  browserStatus: vi.fn(),
  browserClose: vi.fn(),
}));

vi.mock('@services/aiSidecar', () => ({
  browserNavigate: browserMocks.browserNavigate,
  browserAction: browserMocks.browserAction,
  browserSnapshot: browserMocks.browserSnapshot,
  browserStatus: browserMocks.browserStatus,
  browserClose: browserMocks.browserClose,
  buildSidecarSecurityContext: vi.fn(() => ({
    settingsLocked: false,
    permissionsNetwork: true,
    locale: 'fr',
  })),
  isBrowserLockedError: (message: string) => message.includes('browser_locked'),
}));

const getPluginDataDir = vi.fn().mockResolvedValue('/data/plugins/workproba.browser');

vi.mock('@composables/usePlugins', () => ({
  BROWSER_PLUGIN_ID: 'workproba.browser',
  usePlugins: () => ({
    isBrowserPluginActive: ref(true),
    getPluginDataDir,
  }),
}));

vi.mock('@composables/useAppSettings', () => ({
  useAppSettings: () => ({
    settingsLocked: ref(false),
    permissionsNetwork: ref(true),
    locale: ref('fr'),
    codeExecute: ref(true),
    auditEnabled: ref(null),
  }),
}));

import { useBrowser } from '@composables/useBrowser';

describe('useBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    browserMocks.browserNavigate.mockResolvedValue({
      title: 'Example',
      url: 'https://example.com',
      snapshot_yaml: '- heading: Example\n  ref: e1',
      screenshot_b64: 'aGVsbG8=',
    });
    browserMocks.browserAction.mockResolvedValue({
      snapshot_yaml: '- heading: Example\n  ref: e1',
      screenshot_b64: 'aGVsbG8=',
      title: 'Example',
      url: 'https://example.com',
    });
    browserMocks.browserStatus.mockResolvedValue({ active: false, url: '', title: '' });
  });

  it('applyToolResult met à jour url/title/screenshot/snapshot pour browser_navigate', () => {
    const { applyToolResult, currentUrl, title, screenshot, snapshotYaml, active } = useBrowser();
    applyToolResult('browser_navigate', {
      url: 'https://example.com/pricing',
      title: 'Pricing',
      screenshot_b64: 'abc123',
      snapshot_yaml: '- button: Buy\n  ref: e9',
    });
    expect(currentUrl.value).toBe('https://example.com/pricing');
    expect(title.value).toBe('Pricing');
    expect(screenshot.value).toBe('abc123');
    expect(snapshotYaml.value).toContain('e9');
    expect(active.value).toBe(true);
  });

  it('applyToolResult met à jour le panneau pour browser_type', () => {
    const { applyToolResult, snapshotYaml, lastAiAction, highlight } = useBrowser();
    applyToolResult('browser_type', {
      snapshot_yaml: '- textbox: Email\n  ref: e3',
      screenshot_b64: 'typed',
      human_summary: "J'ai saisi du texte dans l'élément e3",
      action_ref: 'e3',
      action_bbox: { x: 10, y: 20, width: 100, height: 32 },
      viewport: { width: 1280, height: 720 },
    });
    expect(snapshotYaml.value).toContain('Email');
    expect(lastAiAction.value?.label).toContain('e3');
    expect(highlight.value?.ref).toBe('e3');
  });

  it('applyToolResult ignore un tool inconnu', () => {
    const { applyToolResult, currentUrl } = useBrowser();
    applyToolResult('list_files', { url: 'https://ignored.test' });
    expect(currentUrl.value).not.toBe('https://ignored.test');
  });

  it('applyToolResult déclenche un snapshot silencieux sans screenshot', async () => {
    browserMocks.browserSnapshot.mockResolvedValue({
      title: 'Fallback',
      url: 'https://example.com',
      snapshot_yaml: '- heading: Fallback',
      screenshot_b64: 'fallback-img',
    });
    const { applyToolResult, screenshot } = useBrowser();
    applyToolResult('browser_click', {
      url: 'https://example.com',
      snapshot_yaml: '- button: Buy',
      action_ref: 'e9',
    });
    await vi.waitFor(() => {
      expect(browserMocks.browserSnapshot).toHaveBeenCalled();
    });
    expect(screenshot.value).toBe('fallback-img');
  });

  it('navigate appelle browserNavigate et mappe browser_locked', async () => {
    browserMocks.browserNavigate.mockRejectedValueOnce(new Error('browser_locked'));
    const { navigate, error } = useBrowser();
    await navigate('https://example.com');
    expect(browserMocks.browserNavigate).toHaveBeenCalledWith(
      '/data/plugins/workproba.browser',
      'https://example.com',
      expect.objectContaining({ settingsLocked: false }),
    );
    expect(error.value).toBe('browser_locked');
  });

  it('goBack appelle browserAction avec action back', async () => {
    const { goBack } = useBrowser();
    await goBack();
    expect(browserMocks.browserAction).toHaveBeenCalledWith(
      '/data/plugins/workproba.browser',
      { action: 'back' },
      expect.any(Object),
    );
  });

  it('pausePilotage et resumePilotage basculent le flag', () => {
    const { pilotagePaused, pausePilotage, resumePilotage } = useBrowser();
    expect(pilotagePaused.value).toBe(false);
    pausePilotage();
    expect(pilotagePaused.value).toBe(true);
    resumePilotage();
    expect(pilotagePaused.value).toBe(false);
  });

  it('setAgentTurnActive active le mode live refresh', () => {
    const { agentTurnActive, setAgentTurnActive } = useBrowser();
    expect(agentTurnActive.value).toBe(false);
    setAgentTurnActive(true);
    expect(agentTurnActive.value).toBe(true);
    setAgentTurnActive(false);
    expect(agentTurnActive.value).toBe(false);
  });
});
