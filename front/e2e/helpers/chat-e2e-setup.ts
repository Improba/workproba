import { expect, type Page, request, test } from '@playwright/test';

export const E2E_PROJECT_PATH = '/tmp/workproba-e2e-project';
export const E2E_WORKSPACE_ID = 'ws-e2e';
export const E2E_SESSION_ID = 'sess-e2e-chat';

const sidecarUrl = process.env.AI_SIDECAR_URL || 'http://127.0.0.1:8765';
const frontPort = process.env.FRONT_DOCKER_PORT_EXPOSED || '5053';
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${frontPort}`;

export async function skipIfFrontUnavailable(): Promise<void> {
  const context = await request.newContext();
  try {
    const resp = await context.get(baseURL, { timeout: 5000 });
    test.skip(!resp.ok(), `Front injoignable sur ${baseURL} (lancez yarn dev ou yarn test:e2e)`);
  } catch {
    test.skip(true, `Front injoignable sur ${baseURL} (lancez yarn dev ou yarn test:e2e)`);
  } finally {
    await context.dispose();
  }
}

export async function installTauriMock(
  page: Page,
  sessionId = E2E_SESSION_ID,
): Promise<void> {
  await page.addInitScript(
    ({ projectPath, workspaceId, sid }) => {
      const now = new Date().toISOString();
      const appSettings = {
        version: 1,
        providers: [] as unknown[],
        density: 'comfortable',
        toolCallView: 'human',
        settingsMode: 'guided',
        settingsLocked: false,
      };

      const workspace = {
        id: workspaceId,
        folderPath: projectPath,
        dataDir: `${projectPath}/.workproba`,
        title: 'Projet e2e',
        createdAt: now,
        lastOpenedAt: now,
      };

      window.__TAURI_INTERNALS__ = window.__TAURI_INTERNALS__ ?? {};
      const callbacks = new Map<number, (data: unknown) => unknown>();

      window.__TAURI_INTERNALS__.transformCallback = (
        callback: (data: unknown) => unknown,
        once = false,
      ) => {
        const id = window.crypto.getRandomValues(new Uint32Array(1))[0];
        callbacks.set(id, (data) => {
          if (once) callbacks.delete(id);
          return callback?.(data);
        });
        return id;
      };
      window.__TAURI_INTERNALS__.unregisterCallback = (id: number) => {
        callbacks.delete(id);
      };
      window.__TAURI_INTERNALS__.runCallback = (id: number, data: unknown) => {
        callbacks.get(id)?.(data);
      };
      window.__TAURI_INTERNALS__.callbacks = callbacks;

      window.__TAURI_INTERNALS__.invoke = async (cmd: string, args: Record<string, unknown> = {}) => {
        switch (cmd) {
          case 'get_app_settings':
            return { ...appSettings, onboardingDone: true };
          case 'save_app_settings':
            Object.assign(appSettings, args.settings as Record<string, unknown>);
            return { ...appSettings };
          case 'find_conversation_by_id':
            return {
              id: String(args.sessionId ?? sid),
              workspaceId,
              folderPath: projectPath,
              title: 'Conversation e2e',
              messages: [],
              createdAt: now,
              updatedAt: now,
            };
          case 'restore_last_project_path':
            return workspace;
          case 'set_active_project_path':
            return {
              ...workspace,
              folderPath: String(args.projectPath ?? projectPath),
              dataDir: `${String(args.projectPath ?? projectPath)}/.workproba`,
            };
          case 'get_active_project_path':
            return projectPath;
          case 'get_workspace_data_dir':
            return `${projectPath}/.workproba`;
          case 'list_documents':
          case 'list_dir_entries':
          case 'list_workspaces':
          case 'list_conversations':
            return [];
          case 'save_conversation':
          case 'delete_conversation':
          case 'open_path':
          case 'reveal_in_os':
            return null;
          default:
            return null;
        }
      };

      window.__TAURI_INTERNALS__.metadata = {
        currentWindow: { label: 'main' },
        currentWebview: { windowLabel: 'main', label: 'main' },
      };

      localStorage.setItem('workproba:activeProjectPath', projectPath);
      localStorage.setItem('workproba:activeWorkspaceId', workspaceId);
      localStorage.setItem('workproba:activeWorkspaceDataDir', `${projectPath}/.workproba`);
      localStorage.setItem('workproba:onboardingDone', 'true');
    },
    {
      projectPath: E2E_PROJECT_PATH,
      workspaceId: E2E_WORKSPACE_ID,
      sid: sessionId,
    },
  );
}

export async function installSidecarHealthMock(page: Page): Promise<void> {
  await page.route(`${sidecarUrl}/health`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok' }),
    });
  });

  await page.route(`${sidecarUrl}/`, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback();
      return;
    }
    await route.fulfill({ status: 200, body: 'ok' });
  });
}

export async function openChatPage(page: Page, sessionId = E2E_SESSION_ID): Promise<void> {
  await page.goto(`/chat/${sessionId}`);
  await expect(page.getByPlaceholder('Écrivez votre message…')).toBeVisible({
    timeout: 15_000,
  });
}

export async function sendChatMessage(page: Page, text: string): Promise<void> {
  const composer = page.getByPlaceholder('Écrivez votre message…');
  await composer.fill(text);
  await page.getByRole('button', { name: 'Envoyer' }).click();
}
