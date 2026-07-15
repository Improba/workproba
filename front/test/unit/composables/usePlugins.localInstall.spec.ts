import { afterEach, describe, expect, it, vi } from 'vitest';

describe('localPluginInstallAvailable', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('autorise l’installation locale en build dev', async () => {
    vi.stubEnv('DEV', true);
    vi.stubEnv('VITE_LOCAL_PLUGIN_INSTALL', '');
    const { localPluginInstallAvailable } = await import('@composables/usePlugins');
    expect(localPluginInstallAvailable()).toBe(true);
  });

  it('autorise l’installation locale quand VITE_LOCAL_PLUGIN_INSTALL=true', async () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_LOCAL_PLUGIN_INSTALL', 'true');
    const { localPluginInstallAvailable } = await import('@composables/usePlugins');
    expect(localPluginInstallAvailable()).toBe(true);
  });

  it('refuse l’installation locale en build produit sans flag', async () => {
    vi.stubEnv('DEV', false);
    vi.stubEnv('VITE_LOCAL_PLUGIN_INSTALL', '');
    const { localPluginInstallAvailable } = await import('@composables/usePlugins');
    expect(localPluginInstallAvailable()).toBe(false);
  });
});
