#!/usr/bin/env node
/**
 * Capture README preview screenshots (light + dark) via Playwright.
 * Requires the Quasar dev server on :5053 (make dev or yarn dev).
 *
 * Usage (from workproba/):
 *   node scripts/capture-readme-screenshots.mjs
 */

import { chromium } from '../front/node_modules/playwright/index.mjs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'docs', 'images');
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5053';
const VIEWPORT = { width: 1600, height: 1000 };
const JPEG_QUALITY = 82;

const PROJECT_PATH = '/home/syl/kaggle';
const WORKSPACE_KAGGLE = 'ws-readme-kaggle';
const WORKSPACE_COR = 'ws-readme-cor';
const SESSION_ID = 'sess-readme-cv';
const PLUGIN_DATA_DIR = '/tmp/workproba-readme-screenshots/plugins/workproba.personas';

const now = new Date();
const iso = (offsetMinutes = 0) =>
  new Date(now.getTime() - offsetMinutes * 60_000).toISOString();

const assistantReply = `Je peux t'aider à structurer ou rédiger ton CV. Pour commencer, j'aurais besoin de quelques précisions :

1. **Quel est ton domaine** (métier, secteur, niveau d'expérience) ?
2. **As-tu déjà un CV** (fichier Word, PDF, texte) que je peux analyser ?
3. **Y a-t-il des éléments précis** à mettre en avant (poste visé, compétences clés, formation) ?

Si tu as un fichier existant dans l'espace, indique-moi son nom et je pourrai le parcourir.`;

const mistralSet = {
  id: 'mistral-default',
  name: 'Mistral',
  description: 'Cloud Improba, tout-intégré.',
  badges: ['Cloud Improba', 'Recommandé'],
  chat: {
    provider: 'mistral',
    model: 'mistral-small-latest',
    baseUrl: 'https://api.mistral.ai/v1',
    apiKeyRef: 'secrets/mistral',
    apiKey: 'readme-screenshot-mock',
    reasoning: 'auto',
    models: [
      {
        model: 'mistral-small-latest',
        label: 'Mistral Small',
        contextWindow: 32000,
        reasoningEfforts: ['none', 'low', 'medium', 'high'],
      },
    ],
  },
  embeddings: {
    provider: 'mistral',
    model: 'mistral-embed',
    baseUrl: 'https://api.mistral.ai/v1',
    apiKeyRef: 'secrets/mistral',
  },
  ocr: { provider: 'mistral', mode: 'auto' },
  vision: { mode: 'chat' },
  capabilities: { reasoning: 'medium', vision: true, tools: true },
  isDefault: true,
  isBuiltin: true,
};

const personasPlugin = {
  manifest: {
    id: 'workproba.personas',
    name: 'plugin.workproba.personas.name',
    version: '1.0.0',
    description: 'plugin.workproba.personas.description',
    permissions: [
      'agent:tools',
      'ui:panels',
      'ui:composer',
      'settings:section',
      'hooks:subscribe',
      'storage:namespace',
      'core.providers.llm',
      'core.memory.search',
      'memory:forget',
    ],
    defaultEnabled: true,
    uiSlots: ['left_panel', 'composer_actions', 'settings', 'side_chat'],
    hooks: [],
    isBuiltin: true,
  },
  enabled: true,
  enabledScoped: true,
  source: 'builtin',
};

const projetPlugin = {
  manifest: {
    id: 'workproba.projet',
    name: 'plugin.workproba.projet.name',
    version: '1.0.0',
    description: 'plugin.workproba.projet.description',
    permissions: ['space:read', 'files:write', 'agent:tools', 'ui:panels'],
    defaultEnabled: false,
    uiSlots: ['right_panel', 'composer_actions', 'settings'],
    hooks: [],
    isBuiltin: true,
  },
  enabled: false,
  enabledScoped: false,
  source: 'builtin',
};

function buildMockPayload() {
  const kaggleWorkspace = {
    id: WORKSPACE_KAGGLE,
    folderPath: PROJECT_PATH,
    dataDir: `${PROJECT_PATH}/.workproba`,
    title: 'kaggle',
    createdAt: iso(60 * 24 * 30),
    lastOpenedAt: iso(4),
  };

  const corWorkspace = {
    id: WORKSPACE_COR,
    folderPath: '/home/syl/cor',
    dataDir: '/home/syl/cor/.workproba',
    title: 'cor',
    createdAt: iso(60 * 24 * 60),
    lastOpenedAt: iso(60 * 24 * 2),
  };

  const conversations = [
    {
      id: SESSION_ID,
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Besoin aide pour créer CV',
      messages: [
        {
          id: 'msg-user-1',
          role: 'user',
          content: 'salut, je suis en train d\'essayer de faire mon cv',
          createdAt: iso(6),
        },
        {
          id: 'msg-assistant-1',
          role: 'assistant',
          content: assistantReply,
          createdAt: iso(5),
        },
      ],
      reasoningEffort: null,
      model: 'mistral-small-latest',
      createdAt: iso(30),
      updatedAt: iso(4),
    },
    {
      id: 'sess-arc',
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Besoin d\'aide sur ARC-AGI-3',
      messages: [],
      createdAt: iso(90),
      updatedAt: iso(60),
    },
    {
      id: 'sess-new-1',
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Nouvelle conversation',
      messages: [],
      createdAt: iso(18 * 60),
      updatedAt: iso(18 * 60),
    },
    {
      id: 'sess-new-2',
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Nouvelle conversation',
      messages: [],
      createdAt: iso(21 * 60),
      updatedAt: iso(21 * 60),
    },
    {
      id: 'sess-extra-1',
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Notes réunion produit',
      messages: [],
      createdAt: iso(48 * 60),
      updatedAt: iso(48 * 60),
    },
    {
      id: 'sess-extra-2',
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Idées roadmap Q3',
      messages: [],
      createdAt: iso(72 * 60),
      updatedAt: iso(72 * 60),
    },
    {
      id: 'sess-extra-3',
      workspaceId: WORKSPACE_KAGGLE,
      folderPath: PROJECT_PATH,
      title: 'Brouillon email client',
      messages: [],
      createdAt: iso(96 * 60),
      updatedAt: iso(96 * 60),
    },
  ];

  const appSettings = {
    version: 1,
    providers: [],
    density: 'comfortable',
    toolCallView: 'human',
    settingsMode: 'guided',
    settingsLocked: false,
    onboardingDone: true,
    profileOnboardingDone: true,
    userName: 'Sylvain Improba',
    userOrg: 'Improba',
    activeSetId: 'mistral-default',
    sets: [mistralSet],
    locale: 'fr',
  };

  const dirEntries = [
    {
      name: 'ARC-AGI-3',
      relativePath: 'ARC-AGI-3',
      isDir: true,
      kind: 'directory',
    },
    {
      name: 'token.txt',
      relativePath: 'token.txt',
      isDir: false,
      kind: 'text',
    },
  ];

  return {
    projectPath: PROJECT_PATH,
    workspaceId: WORKSPACE_KAGGLE,
    sessionId: SESSION_ID,
    kaggleWorkspace,
    corWorkspace,
    conversations,
    appSettings,
    dirEntries,
    pluginDataDir: PLUGIN_DATA_DIR,
    plugins: [personasPlugin, projetPlugin],
  };
}

async function installMocks(page, themeId) {
  const payload = buildMockPayload();

  await page.addInitScript(
    ({ data, theme }) => {
      const callbacks = new Map();

      window.__TAURI_INTERNALS__ = window.__TAURI_INTERNALS__ ?? {};
      window.__TAURI_INTERNALS__.transformCallback = (callback, once = false) => {
        const id = window.crypto.getRandomValues(new Uint32Array(1))[0];
        callbacks.set(id, (arg) => {
          if (once) callbacks.delete(id);
          return callback?.(arg);
        });
        return id;
      };
      window.__TAURI_INTERNALS__.unregisterCallback = (id) => callbacks.delete(id);
      window.__TAURI_INTERNALS__.runCallback = (id, arg) => callbacks.get(id)?.(arg);
      window.__TAURI_INTERNALS__.callbacks = callbacks;
      window.__TAURI_INTERNALS__.metadata = {
        currentWindow: { label: 'main' },
        currentWebview: { windowLabel: 'main', label: 'main' },
      };

      const appSettings = { ...data.appSettings, uiTheme: theme };

      window.__TAURI_INTERNALS__.invoke = async (cmd, args = {}) => {
        switch (cmd) {
          case 'get_app_settings':
            return { ...appSettings };
          case 'save_app_settings':
            Object.assign(appSettings, args.settings ?? {});
            return { ...appSettings };
          case 'find_conversation_by_id':
            return (
              data.conversations.find((c) => c.id === String(args.sessionId)) ?? {
                id: data.sessionId,
                workspaceId: data.workspaceId,
                folderPath: data.projectPath,
                title: 'Conversation',
                messages: [],
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              }
            );
          case 'list_conversations':
            return data.conversations.filter((c) => c.workspaceId === args.workspaceId);
          case 'list_workspaces':
            return [data.kaggleWorkspace, data.corWorkspace];
          case 'restore_last_project_path':
            return data.kaggleWorkspace;
          case 'set_active_project_path':
            return data.kaggleWorkspace;
          case 'get_active_project_path':
            return data.projectPath;
          case 'get_workspace_data_dir':
            return `${data.projectPath}/.workproba`;
          case 'list_dir_entries':
            if (String(args.dirRelativePath ?? '') === '') return data.dirEntries;
            return [];
          case 'list_documents':
            return [];
          case 'list_plugins':
            return data.plugins;
          case 'get_plugin_data_dir':
            return data.pluginDataDir;
          case 'is_preset_active':
            return false;
          case 'get_enterprise_preset':
            return null;
          case 'save_conversation':
          case 'delete_conversation':
          case 'open_path':
          case 'reveal_in_os':
          case 'activate_plugin':
          case 'deactivate_plugin':
            return null;
          default:
            return null;
        }
      };

      localStorage.setItem('workproba:activeProjectPath', data.projectPath);
      localStorage.setItem('workproba:activeWorkspaceId', data.workspaceId);
      localStorage.setItem('workproba:activeWorkspaceDataDir', `${data.projectPath}/.workproba`);
      localStorage.setItem('workproba:onboardingDone', 'true');
      localStorage.setItem('workproba:uiTheme', theme);
      localStorage.setItem('workproba:locale', 'fr');
    },
    { data: payload, theme: themeId },
  );
}

async function dismissNotifications(page) {
  const closeButtons = page.locator('.q-notification button');
  const count = await closeButtons.count();
  for (let i = 0; i < count; i += 1) {
    await closeButtons.nth(i).click().catch(() => {});
  }
  await page.waitForTimeout(200);
}

async function waitForShell(page) {
  await page.goto(`${BASE_URL}/chat/${SESSION_ID}`, { waitUntil: 'networkidle' });
  await page.locator('.wp-shell').waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByPlaceholder('Écrivez votre message…').waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForTimeout(800);
  await dismissNotifications(page);
}

async function captureLight(page) {
  await installMocks(page, 'paper');
  await waitForShell(page);

  await page.getByRole('button', { name: 'Ouvrir Regards (Ctrl+Shift+L)' }).click();
  await page.locator('.wp-side-chat').waitFor({ state: 'visible', timeout: 10_000 });
  await page.getByRole('button', { name: 'Choisir les personas' }).click();
  await page.locator('.personas-picker').waitFor({ state: 'visible', timeout: 10_000 });
  try {
    await page.getByText('RH', { exact: true }).waitFor({ state: 'visible', timeout: 12_000 });
  } catch {
    console.warn('Personas picker: liste non chargée, capture avec le panneau ouvert.');
  }
  await page.waitForTimeout(500);
  await dismissNotifications(page);

  await page.locator('.wp-shell').screenshot({
    path: path.join(OUT_DIR, 'workproba-light-mode.jpg'),
    type: 'jpeg',
    quality: JPEG_QUALITY,
  });
}

async function captureDark(page) {
  await installMocks(page, 'charcoal');
  await waitForShell(page);

  await page.getByRole('button', { name: 'Afficher l\'explorateur de fichiers (Ctrl+B)' }).click();
  await page.locator('.wp-right-panel--collapsed').waitFor({ state: 'hidden', timeout: 10_000 });
  await page.getByPlaceholder('Filtrer les fichiers…').waitFor({ state: 'visible', timeout: 10_000 });
  await page.locator('.wp-files__tree .wp-node__label', { hasText: 'ARC-AGI-3' }).waitFor({
    state: 'visible',
    timeout: 10_000,
  });
  await page.waitForTimeout(500);
  await dismissNotifications(page);

  await page.locator('.wp-shell').screenshot({
    path: path.join(OUT_DIR, 'workproba-dark-mode.jpg'),
    type: 'jpeg',
    quality: JPEG_QUALITY,
  });
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
    locale: 'fr-FR',
  });

  try {
    const lightPage = await context.newPage();
    await captureLight(lightPage);
    await lightPage.close();

    const darkPage = await context.newPage();
    await captureDark(darkPage);
    await darkPage.close();

    console.log('Screenshots saved to', OUT_DIR);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
