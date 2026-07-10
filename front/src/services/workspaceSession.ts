import type { ChatMessage, ReasoningEffort } from '#types';
import { normalizeChatMessages } from '@utils/chatMessageNormalize';
import {
  createConversation as createConversationCommand,
  deleteConversation as deleteConversationCommand,
  findConversationById,
  listConversations as listConversationsCommand,
  saveConversation as saveConversationCommand,
} from '@composables/useWorkspaceApi';
import { isDesktopApp } from '@composables/useDesktop';

export interface LocalSession {
  id: string;
  workspaceId: string;
  projectPath: string;
  title: string;
  messages: ChatMessage[];
  reasoningEffort?: ReasoningEffort | null;
  model?: string | null;
  summary?: string | null;
  createdAt: string;
  updatedAt: string;
}

const LEGACY_STORAGE_PREFIX = 'workproba:sessions:';

function legacyStorageKey(projectPath: string): string {
  return `${LEGACY_STORAGE_PREFIX}${projectPath}`;
}

function readLegacyStore(projectPath: string): LocalSession[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const raw = localStorage.getItem(legacyStorageKey(projectPath));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Array<Partial<LocalSession>>;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((session) => session.id && session.projectPath)
      .map((session) => ({
        id: String(session.id),
        workspaceId: String(session.workspaceId ?? ''),
        projectPath: String(session.projectPath),
        title: String(session.title ?? 'Conversation'),
        messages: normalizeChatMessages(session.messages),
        reasoningEffort: (session.reasoningEffort as ReasoningEffort | null | undefined) ?? null,
        model: (session.model as string | null | undefined) ?? null,
        createdAt: String(session.createdAt ?? new Date().toISOString()),
        updatedAt: String(session.updatedAt ?? new Date().toISOString()),
      }));
  } catch {
    return [];
  }
}

function clearLegacyStore(projectPath: string): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(legacyStorageKey(projectPath));
}

async function migrateLegacySessions(
  workspaceId: string,
  projectPath: string,
): Promise<void> {
  const legacySessions = readLegacyStore(projectPath);
  if (!legacySessions.length) return;

  for (const session of legacySessions) {
    await saveConversationCommand({
      id: session.id,
      workspaceId,
      folderPath: projectPath,
      title: session.title,
      messages: normalizeChatMessages(session.messages),
      reasoningEffort: session.reasoningEffort ?? null,
      model: session.model ?? null,
      createdAt: session.createdAt,
      updatedAt: session.updatedAt,
    });
  }

  clearLegacyStore(projectPath);
}

export async function ensureWorkspaceSessions(
  workspaceId: string,
  projectPath: string,
): Promise<void> {
  if (!isDesktopApp()) return;
  await migrateLegacySessions(workspaceId, projectPath);
}

export async function createSession(
  workspaceId: string,
  projectPath: string,
  title?: string,
): Promise<LocalSession> {
  if (!isDesktopApp()) {
    throw new Error('createSession nécessite l’application bureau Tauri');
  }

  const session = await createConversationCommand(workspaceId, projectPath, title);
  return {
    id: session.id,
    workspaceId: session.workspaceId,
    projectPath: session.folderPath,
    title: session.title,
    messages: normalizeChatMessages(session.messages),
    reasoningEffort: session.reasoningEffort ?? null,
    model: session.model ?? null,
    summary: session.summary ?? null,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
  };
}

export async function getSession(sessionId: string): Promise<LocalSession | null> {
  if (!isDesktopApp()) return null;

  const session = await findConversationById(sessionId);
  if (!session) return null;

  return {
    id: session.id,
    workspaceId: session.workspaceId,
    projectPath: session.folderPath,
    title: session.title,
    messages: normalizeChatMessages(session.messages),
    reasoningEffort: session.reasoningEffort ?? null,
    model: session.model ?? null,
    summary: session.summary ?? null,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
  };
}

export async function listSessions(
  workspaceId: string,
  projectPath: string,
): Promise<LocalSession[]> {
  if (!isDesktopApp()) return [];

  await migrateLegacySessions(workspaceId, projectPath);
  const sessions = await listConversationsCommand(workspaceId);
  return sessions.map((session) => ({
    id: session.id,
    workspaceId: session.workspaceId,
    projectPath: session.folderPath,
    title: session.title,
    messages: normalizeChatMessages(session.messages),
    reasoningEffort: session.reasoningEffort ?? null,
    model: session.model ?? null,
    summary: session.summary ?? null,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
  }));
}

export async function saveSession(session: LocalSession): Promise<void> {
  if (!isDesktopApp()) return;

  await saveConversationCommand({
    id: session.id,
    workspaceId: session.workspaceId,
    folderPath: session.projectPath,
    title: session.title,
    messages: session.messages.filter((message) => !message.streaming),
    reasoningEffort: session.reasoningEffort ?? null,
    model: session.model ?? null,
    summary: session.summary ?? null,
    createdAt: session.createdAt,
    updatedAt: new Date().toISOString(),
  });
}

export async function deleteSession(
  workspaceId: string,
  sessionId: string,
): Promise<void> {
  if (!isDesktopApp()) return;
  await deleteConversationCommand(workspaceId, sessionId);
}
