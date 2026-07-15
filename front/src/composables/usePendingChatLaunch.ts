import { ref } from 'vue';
import type { ChatAttachment, ReasoningEffort } from '#types';

export interface PendingChatLaunch {
  text: string;
  attachments: ChatAttachment[];
  reasoningEffort?: ReasoningEffort | null;
  model?: string | null;
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
