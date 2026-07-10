import { defineConfig, devices } from '@playwright/test';

const frontPort = process.env.FRONT_DOCKER_PORT_EXPOSED || '5053';
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${frontPort}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  webServer: {
    command: `FRONT_DOCKER_PORT_EXPOSED=${frontPort} yarn dev --port ${frontPort}`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 120_000,
  },
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
