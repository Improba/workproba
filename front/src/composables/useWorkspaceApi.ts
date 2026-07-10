import type { ChatMessage, ReasoningEffort } from '#types';
import { isDesktopApp } from '@composables/useDesktop';

export interface StoredConversation {
  id: string;
  workspaceId: string;
  folderPath: string;
  title: string;
  messages: ChatMessage[];
  reasoningEffort?: ReasoningEffort | null;
  createdAt: string;
  updatedAt: string;
}

async function tauriInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(command, args);
}

function mapConversation(raw: {
  id: string;
  workspaceId: string;
  folderPath: string;
  title: string;
  messages: ChatMessage[];
  reasoningEffort?: ReasoningEffort | null;
  createdAt: string;
  updatedAt: string;
}): StoredConversation {
  return {
    id: raw.id,
    workspaceId: raw.workspaceId,
    folderPath: raw.folderPath,
    title: raw.title,
    messages: Array.isArray(raw.messages) ? raw.messages : [],
    reasoningEffort: raw.reasoningEffort ?? null,
    createdAt: raw.createdAt,
    updatedAt: raw.updatedAt,
  };
}

export async function listConversations(
  workspaceId: string,
): Promise<StoredConversation[]> {
  if (!isDesktopApp()) return [];
  const sessions = await tauriInvoke<StoredConversation[]>('list_conversations', {
    workspaceId,
  });
  return sessions.map(mapConversation);
}

export async function findConversationById(
  sessionId: string,
): Promise<StoredConversation | null> {
  if (!isDesktopApp()) return null;
  const session = await tauriInvoke<StoredConversation | null>('find_conversation_by_id', {
    sessionId,
  });
  return session ? mapConversation(session) : null;
}

export async function createConversation(
  workspaceId: string,
  folderPath: string,
  title?: string,
): Promise<StoredConversation> {
  if (!isDesktopApp()) {
    throw new Error('createConversation nécessite l’application bureau Tauri');
  }
  const session = await tauriInvoke<StoredConversation>('create_conversation', {
    workspaceId,
    folderPath,
    title,
  });
  return mapConversation(session);
}

export async function saveConversation(session: StoredConversation): Promise<void> {
  if (!isDesktopApp()) return;
  await tauriInvoke<void>('save_conversation', {
    session: {
      id: session.id,
      workspaceId: session.workspaceId,
      folderPath: session.folderPath,
      title: session.title,
      messages: session.messages,
      reasoningEffort: session.reasoningEffort ?? null,
      createdAt: session.createdAt,
      updatedAt: session.updatedAt,
    },
  });
}

export async function deleteConversation(
  workspaceId: string,
  sessionId: string,
): Promise<void> {
  if (!isDesktopApp()) return;
  await tauriInvoke<void>('delete_conversation', { workspaceId, sessionId });
}
