import type { ChatMessage } from '#types';
import type { LocalDocumentEntry } from '@composables/useDesktop.types';
import type { LlmConfigPayload } from '@composables/useAppSettings';

export type UiMode = 'guided' | 'advanced' | 'locked';

export function resolveUiMode(
  settingsLocked: boolean,
  settingsMode: 'guided' | 'advanced',
): UiMode {
  if (settingsLocked) return 'locked';
  return settingsMode;
}

export interface AgentTurnPayload {
  tenant_id: string;
  project_id: string;
  project_path: string;
  workspace_data_dir?: string;
  session_id: string;
  ui_mode?: UiMode;
  history: Array<{
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string | null;
    thinking?: string | null;
  }>;
  message: string;
  llm_provider_config?: LlmConfigPayload | null;
  embedding_config?: LlmConfigPayload | null;
  context_window?: number | null;
  auto_compact?: boolean;
  documents: Array<{
    id: string;
    name: string;
    mime_type?: string;
    metadata?: Record<string, unknown>;
  }>;
}

export function getAiSidecarUrl(): string {
  return process.env.AI_SIDECAR_URL ?? 'http://127.0.0.1:8765';
}

export function getDesktopSecret(): string {
  return process.env.DESKTOP_INTERNAL_SECRET ?? 'desktop-dev-secret';
}

export async function healthCheck(): Promise<boolean> {
  const url = getAiSidecarUrl();
  const secret = getDesktopSecret();

  try {
    const response = await fetch(`${url}/health`, {
      headers: { 'X-Internal-Secret': secret },
    });
    if (response.ok) return true;
  } catch {
    // Fallback sur la racine si /health n'est pas encore exposé
  }

  try {
    const response = await fetch(`${url}/`, {
      headers: { 'X-Internal-Secret': secret },
    });
    return response.ok;
  } catch {
    return false;
  }
}

function guessMimeType(filename: string): string | undefined {
  const ext = filename.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    pdf: 'application/pdf',
    md: 'text/markdown',
    txt: 'text/plain',
    json: 'application/json',
    csv: 'text/csv',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
  };
  return ext ? map[ext] : undefined;
}

function parseOptionalInt(value: unknown): number | null {
  if (value == null) return null;
  const n = typeof value === 'number' ? value : parseInt(String(value), 10);
  return Number.isFinite(n) ? n : null;
}

function toSummaryMessages(messages: ChatMessage[]): Array<{
  role: 'user' | 'assistant';
  content: string | null;
  thinking?: string | null;
  tool_calls?: Array<{ id: string; name: string; arguments: Record<string, unknown> }>;
}> {
  return messages
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => {
      const entry: ReturnType<typeof toSummaryMessages>[number] = {
        role: m.role,
        content: m.content || null,
      };
      if (m.role === 'assistant') {
        if (m.thinking) entry.thinking = m.thinking;
        if (m.toolCalls?.length) {
          entry.tool_calls = m.toolCalls.map((tc) => ({
            id: tc.id,
            name: tc.name,
            arguments: tc.args ?? {},
          }));
        }
      }
      return entry;
    });
}

function toPythonHistory(messages: ChatMessage[]): AgentTurnPayload['history'] {
  return messages
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => {
      const entry: AgentTurnPayload['history'][number] = {
        role: m.role,
        content: m.content || null,
      };
      if (m.role === 'assistant' && m.thinking) {
        entry.thinking = m.thinking;
      }
      return entry;
    });
}

export function buildAgentTurnPayload(
  sessionId: string,
  projectPath: string,
  message: string,
  history: ChatMessage[],
  documents: LocalDocumentEntry[],
  workspaceDataDir?: string | null,
  llmConfigs?: { chat: LlmConfigPayload | null; embedding: LlmConfigPayload | null } | null,
  uiMode?: UiMode | null,
  contextWindow?: number | null,
  autoCompact: boolean = true,
): AgentTurnPayload {
  return {
    tenant_id: 'desktop',
    project_id: projectPath,
    project_path: projectPath,
    workspace_data_dir: workspaceDataDir ?? undefined,
    session_id: sessionId,
    ui_mode: uiMode ?? undefined,
    history: toPythonHistory(history),
    message,
    llm_provider_config: llmConfigs?.chat ?? undefined,
    embedding_config: llmConfigs?.embedding ?? undefined,
    context_window: contextWindow ?? undefined,
    auto_compact: autoCompact,
    documents: documents.map((doc) => ({
      id: doc.relativePath,
      name: doc.name,
      mime_type: guessMimeType(doc.name),
      metadata: {
        kind: doc.kind,
        relativePath: doc.relativePath,
      },
    })),
  };
}

export interface WorkspaceIndexReport {
  project_root: string;
  db_path: string | null;
  enabled: boolean;
  scanned: number;
  indexed: number;
  unchanged: number;
  skipped: number;
  errors: number;
  total_chars: number;
  truncated: boolean;
  truncation_reason: string | null;
  indexed_paths: string[];
  skipped_paths: string[];
  error_paths: string[];
  metadata: Record<string, unknown>;
}

export interface IndexWorkspaceOptions {
  projectPath: string;
  workspaceDataDir?: string | null;
  embeddingConfig?: LlmConfigPayload | null;
  maxFiles?: number | null;
  /** Restreint l'indexation à ces chemins relatifs (re-index incrémental). */
  paths?: string[] | null;
}

export async function indexWorkspace(opts: IndexWorkspaceOptions): Promise<WorkspaceIndexReport> {
  const response = await fetch(`${getAiSidecarUrl()}/agent/index-workspace`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': getDesktopSecret(),
    },
    body: JSON.stringify({
      project_path: opts.projectPath,
      workspace_data_dir: opts.workspaceDataDir ?? null,
      embedding_config: opts.embeddingConfig ?? null,
      max_files: opts.maxFiles ?? null,
      paths: opts.paths ?? null,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Indexation impossible (HTTP ${response.status}) ${body}`.trim());
  }

  return (await response.json()) as WorkspaceIndexReport;
}

export type RagStatus = 'idle' | 'indexing' | 'done' | 'error' | 'disabled';

/** Vrai quand l'analyse n'a rien eu de nouveau à indexer : tout était déjà à jour. */
export function ragIsUpToDate(report: WorkspaceIndexReport | null): boolean {
  return !!report && report.indexed === 0 && report.errors === 0;
}

export async function requestTitle(opts: {
  firstUserMessage: string;
  firstAssistantReply: string;
  chatConfig?: LlmConfigPayload | null;
  utilityConfig?: LlmConfigPayload | null;
}): Promise<string> {
  const response = await fetch(`${getAiSidecarUrl()}/util/title`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': getDesktopSecret(),
    },
    body: JSON.stringify({
      first_user_message: opts.firstUserMessage,
      first_assistant_reply: opts.firstAssistantReply,
      llm_provider_config: opts.chatConfig ?? null,
      utility_llm_config: opts.utilityConfig ?? null,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(body || `HTTP ${response.status}`);
  }

  const data = (await response.json()) as { title?: string };
  return String(data.title ?? '');
}

export async function requestSummary(opts: {
  messages: ChatMessage[];
  chatConfig?: LlmConfigPayload | null;
  utilityConfig?: LlmConfigPayload | null;
  focus?: string | null;
}): Promise<{ summary: string; inputTokens?: number; outputTokens?: number }> {
  const response = await fetch(`${getAiSidecarUrl()}/util/summarize`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': getDesktopSecret(),
    },
    body: JSON.stringify({
      messages: toSummaryMessages(opts.messages),
      llm_provider_config: opts.chatConfig ?? null,
      utility_llm_config: opts.utilityConfig ?? null,
      focus: opts.focus ?? null,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(body || `HTTP ${response.status}`);
  }

  const data = (await response.json()) as {
    summary?: string;
    input_tokens?: number;
    output_tokens?: number;
  };
  return {
    summary: String(data.summary ?? ''),
    inputTokens: parseOptionalInt(data.input_tokens) ?? undefined,
    outputTokens: parseOptionalInt(data.output_tokens) ?? undefined,
  };
}

/** Libellé court, lisible par un humain (pas de jargon technique). */
export function ragStatusLabel(status: RagStatus, report: WorkspaceIndexReport | null): string {
  switch (status) {
    case 'indexing':
      return 'Analyse des documents…';
    case 'error':
      return "Mémoire : analyse en échec";
    case 'disabled':
      return 'Mémoire désactivée';
    case 'done': {
      if (!report) return 'Mémoire prête';
      if (ragIsUpToDate(report) && report.unchanged > 0) return 'Mémoire à jour';
      if (ragIsUpToDate(report) && report.unchanged === 0) return 'Mémoire prête';
      const added = report.indexed;
      let label: string;
      if (added > 0) label = `Mémoire à jour · ${added} ajouté${added > 1 ? 's' : ''}`;
      else if (report.errors > 0) label = `Mémoire · ${report.errors} erreur${report.errors > 1 ? 's' : ''}`;
      else label = 'Mémoire à jour';
      if (report.truncated) label += ' · limite atteinte';
      return label;
    }
    default:
      return 'Mémoire inactive';
  }
}

