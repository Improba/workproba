import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@services/aiSidecar', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@services/aiSidecar')>();
  return {
    ...actual,
    getAiSidecarUrl: () => 'http://127.0.0.1:8765',
    getDesktopSecret: () => 'desktop-dev-secret',
  };
});

import {
  browserAction,
  browserNavigate,
  isBrowserLockedError,
} from '@services/aiSidecar';

describe('aiSidecar browser', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('browserNavigate envoie plugin_data_dir et security context', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        title: 'Example',
        url: 'https://example.com',
        snapshot_yaml: 'yaml',
        screenshot_b64: 'img',
      }),
    } as Response);

    await browserNavigate('/data/browser', 'https://example.com', {
      settingsLocked: false,
      permissionsNetwork: true,
      locale: 'fr',
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('http://127.0.0.1:8765/plugins/browser/navigate');
    const body = JSON.parse(String(init.body));
    expect(body.plugin_data_dir).toBe('/data/browser');
    expect(body.url).toBe('https://example.com');
    expect(body.settings_locked).toBe(false);
    expect(body.permissions_network).toBe(true);
  });

  it('browserAction sérialise ref/text/direction', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        snapshot_yaml: 'yaml',
        screenshot_b64: 'img',
      }),
    } as Response);

    await browserAction(
      '/data/browser',
      { action: 'type', ref: 'e2', text: 'hello' },
      { settingsLocked: false, permissionsNetwork: true, locale: 'fr' },
    );

    const body = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(body.action).toBe('type');
    expect(body.ref).toBe('e2');
    expect(body.text).toBe('hello');
  });

  it('isBrowserLockedError détecte les messages verrouillés', () => {
    expect(isBrowserLockedError('browser_locked')).toBe(true);
    expect(isBrowserLockedError('Navigateur interdit en mode verrouillé')).toBe(true);
    expect(isBrowserLockedError('forbidden in locked mode')).toBe(true);
    expect(isBrowserLockedError('network error')).toBe(false);
  });
});
