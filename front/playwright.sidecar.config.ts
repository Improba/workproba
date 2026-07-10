import { defineConfig, devices } from '@playwright/test';

type WebServerConfig = {
  command: string;
  url: string;
  reuseExistingServer: boolean;
  timeout: number;
  cwd?: string;
};

/**
 * Config Playwright dédiée au parcours front <-> sidecar Python, SANS webview Tauri.
 *
 * But : valider le branchement réel (badge « Sidecar connecté », streaming SSE, tool
 * calls) dans un navigateur Chromium, sur les trois OS, sans builder l'app desktop.
 *
 * Usage :
 *   yarn test:e2e:sidecar                 # le sidecar doit tourner (make dev-ai)
 *   E2E_START_SIDECAR=1 yarn test:e2e:sidecar  # Playwright lance aussi le sidecar
 *
 * Sous Windows, fournir la commande d'activation du venv :
 *   AI_SIDECAR_CMD=".venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765" \
 *     E2E_START_SIDECAR=1 yarn test:e2e:sidecar
 */

const frontPort = process.env.FRONT_DOCKER_PORT_EXPOSED || '5053';
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${frontPort}`;
const sidecarUrl = process.env.AI_SIDECAR_URL || 'http://127.0.0.1:8765';
const sidecarCmd =
  process.env.AI_SIDECAR_CMD || './run_dev.sh';

const frontServer: WebServerConfig = {
  command: `FRONT_DOCKER_PORT_EXPOSED=${frontPort} yarn dev --port ${frontPort}`,
  url: baseURL,
  reuseExistingServer: true,
  timeout: 120_000,
};

const sidecarServer: WebServerConfig = {
  command: sidecarCmd,
  cwd: '../services/ai',
  url: `${sidecarUrl}/health`,
  reuseExistingServer: true,
  timeout: 60_000,
};

const webServers: WebServerConfig[] = [frontServer];
if (process.env.E2E_START_SIDECAR === '1') {
  webServers.push(sidecarServer);
}

export default defineConfig({
  testDir: './e2e-sidecar',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  webServer: webServers,
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
