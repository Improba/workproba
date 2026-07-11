import type { ChatAttachment, ChatMessage } from '#types';
import type { LocalDocumentEntry, ProviderSet } from '@composables/useDesktop.types';
import type { LlmConfigPayload } from '@composables/useAppSettings';
import { toSidecarLocale } from '@boot/i18n';
import { t } from '@utils/i18nT';
import { providerSetToSidecar } from '@utils/providerSets';

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
  locale?: 'fr' | 'en';
  history: Array<{
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string | null;
    thinking?: string | null;
  }>;
  message: string;
  llm_provider_config?: LlmConfigPayload | null;
  embedding_config?: LlmConfigPayload | null;
  provider_set?: Record<string, unknown> | null;
  context_window?: number | null;
  auto_compact?: boolean;
  documents: Array<{
    id: string;
    name: string;
    mime_type?: string;
    content_base64?: string;
    kind?: string;
    size_bytes?: number;
    metadata?: Record<string, unknown>;
  }>;
  active_plugins?: string[];
  plugin_data_dir?: string;
  settings_locked?: boolean;
  permissions_network?: boolean;
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
  tool_calls?: Array<{
    id: string;
    name: string;
    arguments: Record<string, unknown>;
  }>;
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
  llmConfigs?: {
    chat: LlmConfigPayload | null;
    embedding: LlmConfigPayload | null;
  } | null,
  uiMode?: UiMode | null,
  contextWindow?: number | null,
  autoCompact: boolean = true,
  attachments?: ChatAttachment[],
  locale?: string | null,
  providerSet?: ProviderSet | null,
  activePlugins?: string[] | null,
  pluginDataDir?: string | null,
  security?: SidecarSecurityContext | null,
): AgentTurnPayload {
  const projectDocs = documents.map((doc) => ({
    id: doc.relativePath,
    name: doc.name,
    mime_type: guessMimeType(doc.name),
    metadata: {
      kind: doc.kind,
      relativePath: doc.relativePath,
    },
  }));
  const attachmentDocs = (attachments ?? []).map((att) => ({
    id: att.id,
    name: att.fileName,
    mime_type: att.mimeType || guessMimeType(att.fileName),
    content_base64: att.contentBase64,
    kind: att.kind,
    size_bytes: att.sizeBytes,
    metadata: {
      source: 'chat-attachment',
      kind: att.kind,
    },
  }));
  return {
    tenant_id: 'desktop',
    project_id: projectPath,
    project_path: projectPath,
    workspace_data_dir: workspaceDataDir ?? undefined,
    session_id: sessionId,
    ui_mode: uiMode ?? undefined,
    locale: locale ? toSidecarLocale(locale) : undefined,
    history: toPythonHistory(history),
    message,
    provider_set: providerSet ? providerSetToSidecar(providerSet) : undefined,
    llm_provider_config: providerSet ? undefined : (llmConfigs?.chat ?? undefined),
    embedding_config: providerSet ? undefined : (llmConfigs?.embedding ?? undefined),
    context_window: contextWindow ?? undefined,
    auto_compact: autoCompact,
    documents: [...projectDocs, ...attachmentDocs],
    active_plugins:
      activePlugins && activePlugins.length > 0 ? activePlugins : undefined,
    plugin_data_dir: pluginDataDir ?? undefined,
    settings_locked: security?.settingsLocked ?? undefined,
    permissions_network: security?.permissionsNetwork ?? undefined,
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

export async function indexWorkspace(
  opts: IndexWorkspaceOptions,
): Promise<WorkspaceIndexReport> {
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
    throw new Error(
      `Indexation impossible (HTTP ${response.status}) ${body}`.trim(),
    );
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

export type DocumentPreviewType =
  | 'docx'
  | 'xlsx'
  | 'pdf'
  | 'text'
  | 'image'
  | 'unsupported';

export interface DocumentPreviewResult {
  type: DocumentPreviewType;
  title: string;
  html: string;
}

/** Vérifie qu'un chemin relatif est sûr (anti path traversal côté front). */
export function isSafeRelativePath(path: string): boolean {
  const normalized = path.replace(/\\/g, '/').trim();
  if (!normalized || normalized.startsWith('/') || /^[A-Za-z]:/.test(normalized)) {
    return false;
  }
  return !normalized.split('/').some((segment) => segment === '..');
}

export async function fetchDocumentPreview(opts: {
  relativePath: string;
  projectPath: string;
  workspaceDataDir?: string | null;
}): Promise<DocumentPreviewResult> {
  if (!isSafeRelativePath(opts.relativePath)) {
    throw new Error(t('shell.previewInvalidPath'));
  }

  const params = new URLSearchParams({
    path: opts.relativePath,
    project_path: opts.projectPath,
  });
  if (opts.workspaceDataDir) {
    params.set('workspace_data_dir', opts.workspaceDataDir);
  }

  const response = await fetch(
    `${getAiSidecarUrl()}/documents/preview?${params.toString()}`,
    {
      headers: { 'X-Internal-Secret': getDesktopSecret() },
    },
  );

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(
      t('shell.previewFetchFailed', {
        status: response.status,
        detail: body.trim()
          ? t('shell.previewFetchFailedDetail', { detail: body.trim() })
          : '',
      }),
    );
  }

  return (await response.json()) as DocumentPreviewResult;
}

export function chatAttachmentRelativePath(
  sessionId: string,
  attachmentId: string,
  fileName: string,
): string {
  const safeName = fileName.trim().replace(/[^A-Za-z0-9._-]+/g, '_') || 'attachment';
  return `attachments/${sessionId}/${attachmentId}/${safeName}`;
}

export interface ReprocessAttachmentPayload {
  workspaceDataDir: string;
  projectPath: string;
  attachmentId: string;
  filePath: string;
  mimeType: string;
  providerSet?: ProviderSet | null;
  locale?: string | null;
  contentBase64?: string | null;
  persistOnly?: boolean;
}

export interface ReprocessAttachmentResult {
  status_key: string;
  label_locale: string;
  extracted_text?: string;
}

export async function reprocessAttachment(
  payload: ReprocessAttachmentPayload,
): Promise<ReprocessAttachmentResult> {
  const body: Record<string, unknown> = {
    workspace_data_dir: payload.workspaceDataDir,
    project_path: payload.projectPath,
    attachment_id: payload.attachmentId,
    file_path: payload.filePath,
    mime_type: payload.mimeType,
    locale: payload.locale ? toSidecarLocale(payload.locale) : undefined,
    provider_set: payload.providerSet ? providerSetToSidecar(payload.providerSet) : null,
  };
  if (payload.contentBase64) {
    body.content_base64 = payload.contentBase64;
  }
  if (payload.persistOnly) {
    body.persist_only = true;
  }

  const response = await fetch(`${getAiSidecarUrl()}/agent/reprocess-attachment`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Secret': getDesktopSecret(),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      detail.trim()
        ? `reprocess-attachment failed (${response.status}): ${detail.trim()}`
        : `reprocess-attachment failed (${response.status})`,
    );
  }

  return (await response.json()) as ReprocessAttachmentResult;
}

/** Libellé court, lisible par un humain (pas de jargon technique). */
export function ragStatusLabel(
  status: RagStatus,
  report: WorkspaceIndexReport | null,
): string {
  switch (status) {
    case 'indexing':
      return t('shell.ragStatusIndexing');
    case 'error':
      return t('shell.ragStatusError');
    case 'disabled':
      return t('shell.ragStatusDisabled');
    case 'done': {
      if (!report) return t('shell.ragStatusReady');
      if (ragIsUpToDate(report) && report.unchanged > 0)
        return t('shell.ragStatusUpToDate');
      if (ragIsUpToDate(report) && report.unchanged === 0)
        return t('shell.ragStatusReady');
      const added = report.indexed;
      let label: string;
      if (added > 0)
        label = t('shell.ragStatusAdded', added, { count: added });
      else if (report.errors > 0)
        label = t('shell.ragStatusErrors', report.errors, { count: report.errors });
      else label = t('shell.ragStatusUpToDate');
      if (report.truncated) label += t('shell.ragStatusTruncatedSuffix');
      return label;
    }
    default:
      return t('shell.ragStatusInactive');
  }
}

export interface ProjetProject {
  id: string;
  name: string;
  created_at: string;
}

export interface ProjetPublishedDocument {
  id: string;
  name: string;
  project_id: string;
  created_at: string;
  version?: number;
}

function normalizePublishedDocument(
  raw: Record<string, unknown>,
  projectId: string,
): ProjetPublishedDocument {
  const name = String(raw.name ?? '');
  const createdAt = String(raw.created_at ?? raw.published_at ?? '');
  return {
    id: String(raw.id ?? raw.path ?? name),
    name,
    project_id: String(raw.project_id ?? projectId),
    created_at: createdAt,
    version: typeof raw.version === 'number' ? raw.version : undefined,
  };
}

export async function listProjetProjects(
  pluginDataDir: string,
): Promise<ProjetProject[]> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/projet/projects?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { projects?: ProjetProject[] };
    return data.projects ?? [];
  } catch {
    return [];
  }
}

export async function createProjetProject(
  pluginDataDir: string,
  name: string,
): Promise<ProjetProject | null> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/plugins/projet/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': getDesktopSecret(),
      },
      body: JSON.stringify({ plugin_data_dir: pluginDataDir, name }),
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { project?: ProjetProject };
    return data.project ?? null;
  } catch {
    return null;
  }
}

export async function publishToProjet(opts: {
  pluginDataDir: string;
  workspaceDataDir: string;
  projectId: string;
  name: string;
  sourcePath?: string;
  content?: string;
}): Promise<ProjetPublishedDocument | null> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/plugins/projet/publish`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': getDesktopSecret(),
      },
      body: JSON.stringify({
        plugin_data_dir: opts.pluginDataDir,
        source_path: opts.sourcePath ?? undefined,
        content: opts.content ?? undefined,
        workspace_data_dir: opts.workspaceDataDir,
        project_id: opts.projectId,
        name: opts.name,
      }),
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { artefact?: Record<string, unknown> };
    if (!data.artefact) return null;
    return normalizePublishedDocument(data.artefact, opts.projectId);
  } catch {
    return null;
  }
}

export async function listProjetPublishedDocuments(
  pluginDataDir: string,
  projectId: string,
): Promise<ProjetPublishedDocument[]> {
  const params = new URLSearchParams({
    plugin_data_dir: pluginDataDir,
    project_id: projectId,
  });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/projet/artefacts?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { artefacts?: Record<string, unknown>[] };
    return (data.artefacts ?? []).map((item) => normalizePublishedDocument(item, projectId));
  } catch {
    return [];
  }
}

export interface PlanApprovePayload {
  session_id: string;
  plan_id: string;
  approved: boolean;
  modifications?: unknown[];
  turn_id?: string;
}

export async function approveAgentPlan(payload: PlanApprovePayload): Promise<boolean> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/agent/plan/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': getDesktopSecret(),
      },
      body: JSON.stringify(payload),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export interface PreviewChangeResult {
  is_new: boolean;
  is_binary: boolean;
  diff_html: string;
  message: string;
  old_size: number;
  new_size: number;
}

export async function fetchPreviewChange(opts: {
  workspaceDataDir: string;
  projectPath: string;
  filePath: string;
  proposedContent: string;
}): Promise<PreviewChangeResult | null> {
  if (!isSafeRelativePath(opts.filePath)) {
    return null;
  }
  try {
    const response = await fetch(`${getAiSidecarUrl()}/documents/preview-change`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': getDesktopSecret(),
      },
      body: JSON.stringify({
        workspace_data_dir: opts.workspaceDataDir,
        project_path: opts.projectPath,
        file_path: opts.filePath,
        proposed_content: opts.proposedContent,
      }),
    });
    if (!response.ok) return null;
    return (await response.json()) as PreviewChangeResult;
  } catch {
    return null;
  }
}

export interface FileVersionEntry {
  version_id: string;
  created_at: string;
  size: number;
  label: string;
}

export async function listFileVersions(opts: {
  workspaceDataDir: string;
  filePath: string;
}): Promise<FileVersionEntry[]> {
  if (!isSafeRelativePath(opts.filePath)) return [];
  const params = new URLSearchParams({
    workspace_data_dir: opts.workspaceDataDir,
    file_path: opts.filePath,
  });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/versions?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { versions?: FileVersionEntry[] };
    return data.versions ?? [];
  } catch {
    return [];
  }
}

export async function restoreFileVersion(opts: {
  workspaceDataDir: string;
  projectPath: string;
  filePath: string;
  versionId: string;
}): Promise<boolean> {
  if (!isSafeRelativePath(opts.filePath)) return false;
  try {
    const response = await fetch(`${getAiSidecarUrl()}/versions/restore`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': getDesktopSecret(),
      },
      body: JSON.stringify({
        workspace_data_dir: opts.workspaceDataDir,
        project_path: opts.projectPath,
        file_path: opts.filePath,
        version_id: opts.versionId,
      }),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { ok?: boolean };
    return data.ok !== false;
  } catch {
    return false;
  }
}

// --- Personas (Vague 9) ---

export interface PersonaInfo {
  id: string;
  name: string;
  role: string;
  description: string;
  system_prompt?: string;
  avatar_color: string;
  avatar_icon?: string;
}

export interface PersonaSet {
  id: string;
  name: string;
  personas: PersonaInfo[];
}

function parseSseEvents(buffer: string): {
  events: Array<{ type: string; data: Record<string, unknown> }>;
  rest: string;
} {
  const events: Array<{ type: string; data: Record<string, unknown> }> = [];
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const blocks = normalized.split('\n\n');
  const rest = blocks.pop() ?? '';

  for (const block of blocks) {
    const lines = block.split('\n');
    let eventType = 'message';
    const dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }

    if (!dataLines.length) continue;

    try {
      const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>;
      events.push({ type: eventType, data });
    } catch {
      events.push({ type: 'error', data: { message: dataLines.join('\n') } });
    }
  }

  return { events, rest };
}

export async function consumeSseStream(
  response: Response,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) {
    throw new Error('Réponse streaming sans corps');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { events, rest } = parseSseEvents(buffer);
      buffer = rest;
      for (const event of events) {
        onEvent(event.type, event.data);
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}

function sidecarHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Internal-Secret': getDesktopSecret(),
  };
}

export interface SidecarSecurityContext {
  settingsLocked: boolean;
  permissionsNetwork: boolean;
  locale?: string | null;
}

export function buildSidecarSecurityContext(
  settingsLocked: boolean,
  permissionsNetwork: boolean,
  locale?: string | null,
): SidecarSecurityContext {
  return {
    settingsLocked,
    permissionsNetwork,
    locale: locale ?? undefined,
  };
}

function sidecarSecurityPayload(
  security?: SidecarSecurityContext | null,
): Record<string, unknown> {
  if (!security) return {};
  return {
    settings_locked: security.settingsLocked,
    permissions_network: security.permissionsNetwork,
    locale: security.locale ? toSidecarLocale(security.locale) : undefined,
  };
}

export function parseSidecarErrorDetail(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return '';
  try {
    const parsed = JSON.parse(trimmed) as { detail?: unknown };
    if (typeof parsed.detail === 'string') return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      return parsed.detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg?: unknown }).msg ?? '');
          }
          return '';
        })
        .filter(Boolean)
        .join(' ');
    }
  } catch {
    /* corps brut */
  }
  return trimmed;
}

export function isBrowserLockedError(message: string): boolean {
  const lower = message.toLowerCase();
  return (
    lower.includes('browser_locked')
    || lower.includes('interdit en mode verrouillé')
    || lower.includes('forbidden in locked mode')
  );
}

export async function fetchPersonasSets(
  pluginDataDir: string,
): Promise<PersonaSet[]> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/personas/sets?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { sets?: PersonaSet[] };
    return data.sets ?? [];
  } catch {
    return [];
  }
}

export async function savePersonasSet(
  pluginDataDir: string,
  set: PersonaSet,
): Promise<PersonaSet> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  const response = await fetch(
    `${getAiSidecarUrl()}/plugins/personas/sets?${params.toString()}`,
    {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        id: set.id,
        name: set.name,
        personas: set.personas,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`save personas set failed (${response.status})`);
  }
  const data = (await response.json()) as { set?: PersonaSet };
  if (!data.set) {
    throw new Error('save personas set failed (empty response)');
  }
  return data.set;
}

export async function deletePersonasSet(
  pluginDataDir: string,
  setId: string,
): Promise<void> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  const response = await fetch(
    `${getAiSidecarUrl()}/plugins/personas/sets/${encodeURIComponent(setId)}?${params.toString()}`,
    {
      method: 'DELETE',
      headers: { 'X-Internal-Secret': getDesktopSecret() },
    },
  );
  if (!response.ok) {
    throw new Error(`delete personas set failed (${response.status})`);
  }
}

export interface AskPersonasPayload {
  pluginDataDir: string;
  personaIds: string[];
  question: string;
  context?: string;
  workspaceDataDir?: string | null;
  includeMemory?: boolean;
  providerSet?: Record<string, unknown> | null;
  locale?: string | null;
}

export async function askPersonasOpinion(
  payload: AskPersonasPayload,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${getAiSidecarUrl()}/plugins/personas/ask`, {
    method: 'POST',
    headers: sidecarHeaders(),
    body: JSON.stringify({
      plugin_data_dir: payload.pluginDataDir,
      persona_ids: payload.personaIds,
      question: payload.question,
      context: payload.context ?? '',
      workspace_data_dir: payload.workspaceDataDir ?? undefined,
      include_memory: payload.includeMemory ?? false,
      provider_set: payload.providerSet ?? null,
      locale: payload.locale ?? undefined,
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`ask personas failed (${response.status})`);
  }
  await consumeSseStream(response, onEvent, signal);
}

export interface StartPersonasMeetingPayload {
  pluginDataDir: string;
  personaIds: string[];
  topic: string;
  rounds?: number;
  meetingId?: string | null;
  workspaceDataDir?: string | null;
  includeMemory?: boolean;
  providerSet?: Record<string, unknown> | null;
  locale?: string | null;
}

export async function startPersonasMeeting(
  payload: StartPersonasMeetingPayload,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${getAiSidecarUrl()}/plugins/personas/meeting`, {
    method: 'POST',
    headers: sidecarHeaders(),
    body: JSON.stringify({
      plugin_data_dir: payload.pluginDataDir,
      persona_ids: payload.personaIds,
      topic: payload.topic,
      rounds: payload.rounds ?? 3,
      meeting_id: payload.meetingId ?? undefined,
      workspace_data_dir: payload.workspaceDataDir ?? undefined,
      include_memory: payload.includeMemory ?? false,
      provider_set: payload.providerSet ?? null,
      locale: payload.locale ?? undefined,
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`meeting failed (${response.status})`);
  }
  await consumeSseStream(response, onEvent, signal);
}

export interface DiscussWithPersonasPayload {
  pluginDataDir: string;
  personaIds: string[];
  message: string;
  history?: Array<{
    role: string;
    content: string;
    persona_id?: string;
    persona_name?: string;
  }>;
  discussionId?: string | null;
  workspaceDataDir?: string | null;
  includeMemory?: boolean;
  providerSet?: Record<string, unknown> | null;
  locale?: string | null;
}

export async function discussWithPersonas(
  payload: DiscussWithPersonasPayload,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${getAiSidecarUrl()}/plugins/personas/discuss`, {
    method: 'POST',
    headers: sidecarHeaders(),
    body: JSON.stringify({
      plugin_data_dir: payload.pluginDataDir,
      persona_ids: payload.personaIds,
      message: payload.message,
      history: payload.history ?? [],
      discussion_id: payload.discussionId ?? null,
      workspace_data_dir: payload.workspaceDataDir ?? undefined,
      include_memory: payload.includeMemory ?? false,
      provider_set: payload.providerSet ?? null,
      locale: payload.locale ?? undefined,
    }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`discuss failed (${response.status})`);
  }
  await consumeSseStream(response, onEvent, signal);
}

export interface PersonasMeetingTranscriptTurn {
  round?: number;
  persona_id?: string;
  persona_name?: string;
  role?: string;
  avatar_color?: string;
  avatar_icon?: string;
  content?: string;
}

export interface PersonasMeetingSummary {
  meeting_id: string;
  topic: string;
  persona_ids: string[];
  rounds: number;
  created_at: string;
}

export interface PersonasMeetingDetail extends PersonasMeetingSummary {
  transcript: string | PersonasMeetingTranscriptTurn[];
  summary?: {
    persona_id?: string;
    persona_name?: string;
    content?: string;
  };
}

export interface PersonasDiscussionSummary {
  discussion_id: string;
  persona_ids: string[];
  created_at: string;
  last_message_at: string;
}

export interface PersonasDiscussionDetail extends PersonasDiscussionSummary {
  messages: Array<{
    role: 'user' | 'persona';
    content: string;
    persona_id?: string;
    persona_name?: string;
  }>;
}

export async function fetchPersonasMeetings(
  pluginDataDir: string,
): Promise<PersonasMeetingSummary[]> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/personas/meetings?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { meetings?: PersonasMeetingSummary[] };
    return data.meetings ?? [];
  } catch {
    return [];
  }
}

export async function fetchPersonasMeeting(
  pluginDataDir: string,
  meetingId: string,
): Promise<PersonasMeetingDetail | null> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/personas/meetings/${encodeURIComponent(meetingId)}?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return null;
    const data = (await response.json()) as { meeting?: PersonasMeetingDetail };
    return data.meeting ?? null;
  } catch {
    return null;
  }
}

export async function fetchPersonasDiscussions(
  pluginDataDir: string,
): Promise<PersonasDiscussionSummary[]> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/personas/discussions?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { discussions?: PersonasDiscussionSummary[] };
    return data.discussions ?? [];
  } catch {
    return [];
  }
}

export async function fetchPersonasDiscussion(
  pluginDataDir: string,
  discussionId: string,
): Promise<PersonasDiscussionDetail | null> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/personas/discussions/${encodeURIComponent(discussionId)}?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return null;
    const data = (await response.json()) as { discussion?: PersonasDiscussionDetail };
    return data.discussion ?? null;
  } catch {
    return null;
  }
}

// --- Mémoire (Vague 9) ---

export type MemoryScope = 'user' | 'project';
export type MemorySearchScope = MemoryScope | 'all';

export interface MemoryItem {
  id: string;
  content: string;
  source: string;
  created_at: string;
  tags: string[];
}

export interface MemorySearchResult {
  id?: string;
  memory_id?: string;
  document_id?: string;
  content: string;
  score?: number;
  source?: string;
  created_at?: string;
  kind?: string;
  memory_scope?: MemoryScope;
}

export async function fetchMemoryItems(
  workspaceDataDir: string,
  scope: MemoryScope = 'project',
): Promise<MemoryItem[]> {
  const params = new URLSearchParams({
    workspace_data_dir: workspaceDataDir,
    memory_scope: scope,
  });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/memory/items?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { memories?: MemoryItem[] };
    return data.memories ?? [];
  } catch {
    return [];
  }
}

export async function searchMemory(
  workspaceDataDir: string,
  query: string,
  scope: MemorySearchScope = 'project',
): Promise<MemorySearchResult[]> {
  const params = new URLSearchParams({
    workspace_data_dir: workspaceDataDir,
    query,
    memory_scope: scope,
  });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/memory/search?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return [];
    const data = (await response.json()) as { results?: MemorySearchResult[] };
    return data.results ?? [];
  } catch {
    return [];
  }
}

export async function addMemoryItem(
  workspaceDataDir: string,
  content: string,
  scope: MemoryScope = 'project',
  tags: string[] = [],
): Promise<MemoryItem | null> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/memory/add`, {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        workspace_data_dir: workspaceDataDir,
        memory_scope: scope,
        content,
        tags,
      }),
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { memory?: MemoryItem };
    return data.memory ?? null;
  } catch {
    return null;
  }
}

export async function forgetMemoryItem(
  workspaceDataDir: string,
  memoryId: string,
  scope: MemoryScope = 'project',
): Promise<boolean> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/memory/forget`, {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        workspace_data_dir: workspaceDataDir,
        memory_scope: scope,
        memory_id: memoryId,
      }),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { ok?: boolean };
    return data.ok !== false;
  } catch {
    return false;
  }
}

export type ForgetMemoryScope = 'all' | 'memories' | 'conversations';

export async function forgetAllMemory(
  workspaceDataDir: string,
  scope: ForgetMemoryScope = 'all',
  memoryScope: MemoryScope = 'project',
): Promise<boolean> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/memory`, {
      method: 'DELETE',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        workspace_data_dir: workspaceDataDir,
        memory_scope: memoryScope,
        scope,
        confirmed: true,
      }),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { ok?: boolean };
    return data.ok !== false;
  } catch {
    return false;
  }
}

// --- Browser (Vague 10) ---

export interface BrowserNavigateResult {
  title: string;
  url: string;
  snapshot_yaml: string;
  screenshot_b64: string;
}

export interface BrowserSnapshotResult {
  snapshot_yaml: string;
  screenshot_b64: string;
  title: string;
  url: string;
}

export interface BrowserActionPayload {
  action: 'click' | 'type' | 'scroll' | 'press' | 'back' | 'forward' | 'extract';
  ref?: string;
  text?: string;
  selector?: string;
  key?: string;
  direction?: string;
}

export interface BrowserActionResult {
  snapshot_yaml: string;
  screenshot_b64: string;
  extracted?: string;
}

export interface BrowserStatusResult {
  active: boolean;
  url: string;
  title: string;
}

export async function browserNavigate(
  pluginDataDir: string,
  url: string,
  security?: SidecarSecurityContext | null,
): Promise<BrowserNavigateResult> {
  const response = await fetch(`${getAiSidecarUrl()}/plugins/browser/navigate`, {
    method: 'POST',
    headers: sidecarHeaders(),
    body: JSON.stringify({
      plugin_data_dir: pluginDataDir,
      url,
      ...sidecarSecurityPayload(security),
    }),
  });
  if (!response.ok) {
    const detail = parseSidecarErrorDetail(await response.text().catch(() => ''));
    throw new Error(detail || `browser navigate failed (${response.status})`);
  }
  return (await response.json()) as BrowserNavigateResult;
}

export async function browserSnapshot(
  pluginDataDir: string,
  security?: SidecarSecurityContext | null,
): Promise<BrowserSnapshotResult> {
  const response = await fetch(`${getAiSidecarUrl()}/plugins/browser/snapshot`, {
    method: 'POST',
    headers: sidecarHeaders(),
    body: JSON.stringify({
      plugin_data_dir: pluginDataDir,
      ...sidecarSecurityPayload(security),
    }),
  });
  if (!response.ok) {
    const detail = parseSidecarErrorDetail(await response.text().catch(() => ''));
    throw new Error(detail || `browser snapshot failed (${response.status})`);
  }
  return (await response.json()) as BrowserSnapshotResult;
}

export async function browserAction(
  pluginDataDir: string,
  payload: BrowserActionPayload,
  security?: SidecarSecurityContext | null,
): Promise<BrowserActionResult> {
  const response = await fetch(`${getAiSidecarUrl()}/plugins/browser/action`, {
    method: 'POST',
    headers: sidecarHeaders(),
    body: JSON.stringify({
      plugin_data_dir: pluginDataDir,
      ...payload,
      ...sidecarSecurityPayload(security),
    }),
  });
  if (!response.ok) {
    const detail = parseSidecarErrorDetail(await response.text().catch(() => ''));
    throw new Error(detail || `browser action failed (${response.status})`);
  }
  return (await response.json()) as BrowserActionResult;
}

export async function browserClose(pluginDataDir: string): Promise<boolean> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/plugins/browser/close`, {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({ plugin_data_dir: pluginDataDir }),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { ok?: boolean };
    return data.ok !== false;
  } catch {
    return false;
  }
}

export async function browserStatus(
  pluginDataDir: string,
): Promise<BrowserStatusResult> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/browser/status?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) {
      return { active: false, url: '', title: '' };
    }
    return (await response.json()) as BrowserStatusResult;
  } catch {
    return { active: false, url: '', title: '' };
  }
}

// --- Estimation coût personas (Vague 10) ---

export type PersonasEstimateMode = 'ask' | 'meeting' | 'discuss';

export interface PersonasCostEstimate {
  estimated_tokens: number;
  estimated_calls: number;
  warning?: string;
}

export async function estimatePersonasCost(opts: {
  pluginDataDir: string;
  personaIds: string[];
  mode: PersonasEstimateMode;
  rounds?: number;
  providerSet?: Record<string, unknown> | null;
  security?: SidecarSecurityContext | null;
}): Promise<PersonasCostEstimate | null> {
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/personas/estimate-cost`,
      {
        method: 'POST',
        headers: sidecarHeaders(),
        body: JSON.stringify({
          plugin_data_dir: opts.pluginDataDir,
          persona_ids: opts.personaIds,
          mode: opts.mode,
          rounds: opts.rounds ?? undefined,
          provider_set: opts.providerSet ?? null,
          ...sidecarSecurityPayload(opts.security),
        }),
      },
    );
    if (!response.ok) return null;
    return (await response.json()) as PersonasCostEstimate;
  } catch {
    return null;
  }
}

// --- Audit (Vague 11) ---

export interface AuditEntry {
  timestamp: string;
  event: string;
  actor: string;
  details: Record<string, unknown> | string;
}

export interface AuditFilters {
  workspaceDataDir: string;
  from?: string | null;
  to?: string | null;
  event?: string | null;
  limit?: number | null;
}

export interface AuditConfig {
  retention_days: number;
  enabled: boolean;
}

export async function fetchAudit(
  filters: AuditFilters,
): Promise<{ entries: AuditEntry[]; total: number }> {
  const params = new URLSearchParams({
    workspace_data_dir: filters.workspaceDataDir,
  });
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  if (filters.event) params.set('event', filters.event);
  if (filters.limit != null) params.set('limit', String(filters.limit));

  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/audit?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) {
      return { entries: [], total: 0 };
    }
    const data = (await response.json()) as {
      entries?: AuditEntry[];
      total?: number;
    };
    return {
      entries: data.entries ?? [],
      total: data.total ?? data.entries?.length ?? 0,
    };
  } catch {
    return { entries: [], total: 0 };
  }
}

export interface AuditConfigOptions {
  retentionDays?: number | null;
  enabled?: boolean | null;
}

export async function fetchAuditConfig(
  workspaceDataDir: string,
  preset?: AuditConfigOptions,
): Promise<AuditConfig | null> {
  const params = new URLSearchParams({ workspace_data_dir: workspaceDataDir });
  if (preset?.retentionDays != null) {
    params.set('audit_retention_days', String(preset.retentionDays));
  }
  if (preset?.enabled != null) {
    params.set('audit_enabled', String(preset.enabled));
  }
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/audit/config?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return null;
    return (await response.json()) as AuditConfig;
  } catch {
    return null;
  }
}

export async function updateAuditConfig(
  workspaceDataDir: string,
  retentionDays: number,
  settingsLocked = false,
): Promise<boolean> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/audit/config`, {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        workspace_data_dir: workspaceDataDir,
        retention_days: retentionDays,
        settings_locked: settingsLocked,
      }),
    });
    return response.ok;
  } catch {
    return false;
  }
}

// --- Cloud (Vague 11) ---

export interface CloudStatus {
  configured: boolean;
  mount_path: string | null;
  last_sync: string | null;
  synced_count: number;
}

export async function fetchCloudStatus(
  pluginDataDir: string,
): Promise<CloudStatus | null> {
  const params = new URLSearchParams({ plugin_data_dir: pluginDataDir });
  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/plugins/cloud/status?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return null;
    return (await response.json()) as CloudStatus;
  } catch {
    return null;
  }
}

export async function syncCloud(opts: {
  pluginDataDir: string;
  projectId: string;
  mountPath: string;
}): Promise<{ synced: string[] }> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/plugins/cloud/sync`, {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        plugin_data_dir: opts.pluginDataDir,
        project_id: opts.projectId,
        mount_path: opts.mountPath,
      }),
    });
    if (!response.ok) {
      return { synced: [] };
    }
    const data = (await response.json()) as { synced?: string[] };
    return { synced: data.synced ?? [] };
  } catch {
    return { synced: [] };
  }
}

export async function configCloud(
  pluginDataDir: string,
  mountPath: string,
): Promise<boolean> {
  try {
    const response = await fetch(`${getAiSidecarUrl()}/plugins/cloud/config`, {
      method: 'POST',
      headers: sidecarHeaders(),
      body: JSON.stringify({
        plugin_data_dir: pluginDataDir,
        mount_path: mountPath,
      }),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { ok?: boolean };
    return data.ok !== false;
  } catch {
    return false;
  }
}

export interface AuditExportFilters {
  workspaceDataDir: string;
  from?: string | null;
  to?: string | null;
  event?: string | null;
}

export async function exportAuditCsv(filters: AuditExportFilters): Promise<Blob | null> {
  const params = new URLSearchParams({
    workspace_data_dir: filters.workspaceDataDir,
    format: 'csv',
  });
  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  if (filters.event) params.set('event', filters.event);

  try {
    const response = await fetch(
      `${getAiSidecarUrl()}/audit/export?${params.toString()}`,
      { headers: { 'X-Internal-Secret': getDesktopSecret() } },
    );
    if (!response.ok) return null;
    return await response.blob();
  } catch {
    return null;
  }
}
