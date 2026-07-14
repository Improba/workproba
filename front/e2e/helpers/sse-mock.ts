import type { Page } from '@playwright/test';
import { E2E_PROJECT_PATH } from './chat-e2e-setup';

const sidecarUrl = process.env.AI_SIDECAR_URL || 'http://127.0.0.1:8765';

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

export function buildSseBody(events: SseEvent[]): string {
  return events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join('');
}

function sseHeaders(): Record<string, string> {
  return {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  };
}

export async function mockAgentTurnSse(page: Page, events: SseEvent[]): Promise<void> {
  const body = buildSseBody(events);
  await page.route(`${sidecarUrl}/agent/turn`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: sseHeaders(),
      body,
    });
  });
}

type BrowserConfirmDecision = 'approve' | 'deny' | null;

interface BrowserSseState {
  confirmDecision: BrowserConfirmDecision;
}

/**
 * Mock fetch navigateur pour un flux SSE avec pause sur confirmation_request.
 * page.route ne streame pas correctement un corps SSE tenu ouvert : le mock
 * s'exécute dans le contexte page pour livrer les events par chunks.
 */
export async function installConfirmationSseMock(
  page: Page,
  toolCallId = 'tc_gen_1',
): Promise<void> {
  await page.addInitScript(
    ({ projectPath, tcId }) => {
      const sseState: BrowserSseState = { confirmDecision: null };
      (window as unknown as { __e2eSseState?: BrowserSseState }).__e2eSseState = sseState;

      const originalFetch = window.fetch.bind(window);
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(
          typeof input === 'string'
            ? input
            : input instanceof URL
              ? input.href
              : input.url,
        );

        if (url.includes('/agent/confirm')) {
          const body = JSON.parse(String(init?.body ?? '{}')) as { decision?: 'approve' | 'deny' };
          sseState.confirmDecision = body.decision ?? null;
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        if (url.includes('/agent/turn')) {
          const stream = new ReadableStream({
            start(controller) {
              const encoder = new TextEncoder();
              const write = (event: string, data: Record<string, unknown>) => {
                controller.enqueue(
                  encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
                );
              };

              write('tool_call_start', {
                tool_call_id: tcId,
                tool_name: 'generate_document',
                arguments: { name: 'contrat_dupont.docx' },
                human_summary: 'Je prépare le document',
              });
              write('confirmation_request', {
                confirmation_id: 'cf_e2e_1',
                tool_call_id: tcId,
                tool_name: 'generate_document',
                action: 'create',
                proposed_path: 'contrat_dupont.docx',
                human_summary: 'Je vais créer contrat_dupont.docx',
              });

              const waitForDecision = () => {
                if (!sseState.confirmDecision) {
                  window.setTimeout(waitForDecision, 25);
                  return;
                }

                if (sseState.confirmDecision === 'approve') {
                  write('tool_call_result', {
                    tool_call_id: tcId,
                    tool_name: 'generate_document',
                    result: {
                      metadata: {
                        path: 'contrat_dupont.docx',
                        version_path: `${projectPath}/.workproba/versions/snap1`,
                      },
                    },
                    is_error: false,
                    human_summary: 'Document créé',
                  });
                } else {
                  write('tool_call_result', {
                    tool_call_id: tcId,
                    tool_name: 'generate_document',
                    result: {
                      content:
                        "workproba:approval_denied L'utilisateur a refusé cette action.",
                    },
                    is_error: true,
                    human_summary: 'Action annulée',
                  });
                }

                write('done', { content: '' });
                controller.close();
              };

              waitForDecision();
            },
          });

          return new Response(stream, {
            status: 200,
            headers: { 'Content-Type': 'text/event-stream' },
          });
        }

        if (url.includes('/versions/restore')) {
          return new Response(
            JSON.stringify({
              ok: true,
              restored_path: 'contrat_dupont.docx',
              version_id: 'v1',
              file_path: 'contrat_dupont.docx',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }

        if (url.includes('/versions?')) {
          return new Response(JSON.stringify({ versions: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        return originalFetch(input, init);
      };
    },
    { projectPath: E2E_PROJECT_PATH, tcId: toolCallId },
  );
}
