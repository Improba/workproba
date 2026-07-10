import { expect, test } from '@playwright/test';

const routerMode = process.env.VUE_ROUTER_MODE || 'history';
const defaultLoginPath =
  routerMode === 'hash' ? '/#/auth/login' : '/auth/login';
const loginPath = process.env.PLAYWRIGHT_LOGIN_PATH || defaultLoginPath;
const registerPath = loginPath.replace(/login(?:\?.*)?$/, 'register');
const resetPasswordBasePath = loginPath.replace(
  /login(?:\?.*)?$/,
  'reset-password'
);
const resetPasswordPath = `${resetPasswordBasePath}${
  resetPasswordBasePath.includes('?') ? '&' : '?'
}token=e2e-reset-token`;
const loginUsername = process.env.PLAYWRIGHT_LOGIN_USERNAME;
const loginPassword = process.env.PLAYWRIGHT_LOGIN_PASSWORD;

test.describe('Auth smoke', () => {
  test('la page de login est affichée', async ({ page }) => {
    await page.goto(loginPath);

    await expect(page.locator('input[type="email"]').first()).toBeVisible();
    await expect(page.locator('input[type="password"]').first()).toBeVisible();
  });

  test('login puis redirection hors page auth', async ({ page }) => {
    await page.goto(loginPath);

    const emailInput = page.locator('input[type="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    if (!loginUsername || !loginPassword) {
      await expect(emailInput).toBeVisible();
      await expect(passwordInput).toBeVisible();
      return;
    }

    await emailInput.fill(loginUsername!);
    await passwordInput.fill(loginPassword!);
    await passwordInput.press('Enter');

    await expect
      .poll(() => page.url(), { timeout: 15000 })
      .not.toContain('auth/login');
  });

  test("sur login, l'action register est désactivée", async ({ page }) => {
    await page.goto(loginPath);

    const registerButton = page.getByRole('button', { name: 'Register' }).first();
    await expect(registerButton).toBeVisible();
    await expect(registerButton).toBeDisabled();
  });

  test("l'accès direct à register affiche la page d'inscription", async ({ page }) => {
    await page.goto(registerPath);
    await expect(page).toHaveURL(/auth\/register/);
    await expect(page.locator('.q-banner.bg-warning')).toBeVisible();
  });

  test('mot de passe oublié affiche une bannière après appel backend', async ({
    page,
  }) => {
    await page.route('**/auth-jwt/forgot-password', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.goto(loginPath);
    await page.locator('input[type="email"]').first().fill('playwright@test.local');

    const forgotPasswordLink = page.locator('span.clickable').first();
    await forgotPasswordLink.click();

    await expect(page.locator('.q-banner')).toBeVisible();
  });

  test('mot de passe oublié avec email invalide affiche une erreur', async ({
    page,
  }) => {
    await page.goto(loginPath);
    await page.locator('input[type="email"]').first().fill('invalid-email');

    const forgotPasswordLink = page.locator('span.clickable').first();
    await forgotPasswordLink.click();

    await expect(page.locator('.q-banner.bg-danger')).toBeVisible();
  });

  test('l’accès direct à reset password affiche le formulaire', async ({
    page,
  }) => {
    await page.goto(resetPasswordPath);

    await expect(page).toHaveURL(/auth\/reset-password/);
    await expect(page.getByText('Reset password')).toBeVisible();
  });
});
