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
  }>;
  message: string;
  llm_provider_config?: LlmConfigPayload | null;
  embedding_config?: LlmConfigPayload | null;
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

function toPythonHistory(messages: ChatMessage[]): AgentTurnPayload['history'] {
  return messages
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({
      role: m.role,
      content: m.content || null,
    }));
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
