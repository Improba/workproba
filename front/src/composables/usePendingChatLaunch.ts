import { ref } from 'vue';
import type { ChatAttachment, ReasoningEffort } from '#types';

export interface PendingChatLaunch {
  text?: string;
  attachments?: ChatAttachment[];
  reasoningEffort?: ReasoningEffort | null;
  model?: string | null;
  personasAction?: 'avis' | 'meeting' | 'discussion';
  /** Session créée pour ce lancement : évite d'appliquer le pending sur une autre conversation. */
  sessionId?: string;
}

const pending = ref<PendingChatLaunch | null>(null);

export function setPendingChatLaunch(launch: PendingChatLaunch): void {
  pending.value = launch;
}

export function consumePendingChatLaunch(): PendingChatLaunch | null {
  const launch = pending.value;
  pending.value = null;
  return launch;
}

/** Consomme le lancement s'il vise cette session, ou s'il n'a pas d'id. */
export function consumePendingChatLaunchForSession(
  sessionId: string,
): PendingChatLaunch | null {
  const launch = pending.value;
  if (!launch) return null;
  if (launch.sessionId && launch.sessionId !== sessionId) return null;
  pending.value = null;
  return launch;
}

export function resetPendingChatLaunchForTests(): void {
  pending.value = null;
}
