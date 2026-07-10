import { expect, test } from '@playwright/test';
import {
  E2E_SESSION_ID,
  installSidecarHealthMock,
  installTauriMock,
  openChatPage,
  sendChatMessage,
  skipIfFrontUnavailable,
} from './helpers/chat-e2e-setup';
import { mockAgentTurnSse } from './helpers/sse-mock';

const TECHNICAL_TOOL_NAMES = [
  'read_documents',
  'generate_document',
  'search_kb',
  'list_files',
  'run_code',
];

test.describe('T-D1c anti-jargon (vue humaine tool call)', () => {
  test.beforeAll(async () => {
    await skipIfFrontUnavailable();
  });

  test('masque le jargon technique en vue humaine, visible après bascule', async ({
    page,
  }) => {
    await installTauriMock(page);
    await installSidecarHealthMock(page);
    await mockAgentTurnSse(page, [
      {
        event: 'tool_call_start',
        data: {
          tool_call_id: 'tc_read_1',
          tool_name: 'read_documents',
          arguments: { paths: ['notes.md'], query: 'budget' },
          human_summary: "J'ai consulté vos notes",
        },
      },
      {
        event: 'tool_call_result',
        data: {
          tool_call_id: 'tc_read_1',
          tool_name: 'read_documents',
          result: { excerpts: [{ path: 'notes.md', text: 'Budget 2026' }] },
          is_error: false,
          human_summary: "J'ai consulté vos notes",
        },
      },
      { event: 'done', data: { content: '' } },
    ]);

    await openChatPage(page, E2E_SESSION_ID);
    await sendChatMessage(page, 'Lis mes notes');

    const card = page.getByTestId('tool-call-card').first();
    await expect(card).toBeVisible({ timeout: 15_000 });

    const human = card.locator('.tool-call-card__human');
    await expect(human).toBeVisible();
    await expect(human).toContainText("J'ai consulté vos notes");
    await expect(card.locator('.tool-call-card__tech')).toHaveCount(0);

    const humanText = (await human.innerText()).trim();
    expect(humanText).not.toContain('Arguments');
    expect(humanText).not.toContain('Résultat');
    expect(humanText).not.toMatch(/[{}]/);
    for (const toolName of TECHNICAL_TOOL_NAMES) {
      expect(humanText).not.toContain(toolName);
    }

    await card.getByRole('button', { name: 'Vue technique' }).click();

    const tech = card.locator('.tool-call-card__tech');
    await expect(tech).toBeVisible();
    await expect(tech).toContainText('read_documents');
    await expect(tech.getByText('Arguments')).toBeVisible();
    await expect(tech.getByText('Résultat')).toBeVisible();
    await expect(tech.locator('.tool-call-card__json').first()).toContainText('{');
  });
});
