import { expect, test } from '@playwright/test';
import {
  E2E_SESSION_ID,
  installSidecarHealthMock,
  installTauriMock,
  openChatPage,
  sendChatMessage,
  skipIfFrontUnavailable,
} from './helpers/chat-e2e-setup';
import { installConfirmationSseMock } from './helpers/sse-mock';

test.describe('T-D3e scénario Sylvie (confirmation et restauration)', () => {
  test.beforeAll(async () => {
    await skipIfFrontUnavailable();
  });

  test('Continuer : écriture, bandeau restauration, puis succès au clic Restaurer', async ({
    page,
  }) => {
    await installTauriMock(page);
    await installSidecarHealthMock(page);
    await installConfirmationSseMock(page);

    await openChatPage(page, E2E_SESSION_ID);
    await sendChatMessage(page, 'Crée le contrat Dupont');

    const confirmation = page.getByTestId('confirmation-card');
    await expect(confirmation).toBeVisible({ timeout: 15_000 });
    await expect(confirmation).toContainText('Je vais créer');
    await expect(confirmation.getByRole('button', { name: 'Annuler' })).toBeVisible();
    await expect(confirmation.getByRole('button', { name: 'Continuer' })).toBeVisible();

    await confirmation.getByRole('button', { name: 'Continuer' }).click();

    await expect(confirmation).toBeHidden({ timeout: 10_000 });

    const card = page.getByTestId('tool-call-card').first();
    await expect(card.locator('.tool-call-card__dot--success')).toBeVisible({
      timeout: 10_000,
    });

    const restoreBanner = page.getByTestId('restore-banner');
    await expect(restoreBanner).toBeVisible();
    await expect(restoreBanner).toContainText('Sauvegarde créée.');
    await expect(restoreBanner.getByRole('button', { name: 'Restaurer' })).toBeVisible();

    await restoreBanner.getByRole('button', { name: 'Restaurer' }).click();

    await expect(page.locator('.q-notification')).toContainText('Version restaurée', {
      timeout: 10_000,
    });
  });

  test('Annuler : carte confirmation disparaît, pas de restauration, statut annulé', async ({
    page,
  }) => {
    await installTauriMock(page);
    await installSidecarHealthMock(page);
    await installConfirmationSseMock(page);

    await openChatPage(page, E2E_SESSION_ID);
    await sendChatMessage(page, 'Crée le contrat Dupont');

    const confirmation = page.getByTestId('confirmation-card');
    await expect(confirmation).toBeVisible({ timeout: 15_000 });

    await confirmation.getByRole('button', { name: 'Annuler' }).click();

    await expect(confirmation).toBeHidden({ timeout: 10_000 });
    await expect(page.getByTestId('restore-banner')).toHaveCount(0);

    const card = page.getByTestId('tool-call-card').first();
    await expect(card).toContainText('Action annulée', { timeout: 10_000 });
    await expect(card.locator('.tool-call-card__dot--error')).toBeVisible();
  });
});
