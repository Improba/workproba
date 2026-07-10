import { expect, request, test } from '@playwright/test';

const sidecarUrl = process.env.AI_SIDECAR_URL || 'http://127.0.0.1:8765';

/**
 * Smoke front <-> sidecar : on charge le shell desktop (/home) dans Chromium et on
 * vérifie que le badge de statut passe à « Sidecar connecté » grâce au polling de
 * `useSidecarHealth`. Aucune webview Tauri impliquée.
 */
test.describe('Sidecar health (front <-> Python)', () => {
  test('le badge sidebar passe à « Sidecar connecté »', async ({ page }) => {
    const context = await request.newContext();
    let healthy = false;
    try {
      const resp = await context.get(`${sidecarUrl}/health`, {
        timeout: 3000,
      });
      healthy = resp.ok();
    } catch {
      // healthy reste false : sidecar injoignable, le test sera skippé.
    } finally {
      await context.dispose();
    }

    test.skip(!healthy, 'sidecar Python injoignable sur /health (lancez `make dev-ai`)');

    await page.goto('/home');

    const statusText = page.locator('.wp-sidebar__status-text');
    await expect(statusText).toBeVisible();
    await expect(statusText).toHaveText('Sidecar connecté', { timeout: 15_000 });
  });
});
