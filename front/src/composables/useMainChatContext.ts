import { readonly, ref } from 'vue';
import type { ChatMessage } from '#types';
import { formatMainChatContext } from '@utils/mainChatContext';

const messages = ref<ChatMessage[]>([]);
const activeSessionId = ref<string | null>(null);

export function resetMainChatContextForTests(): void {
  messages.value = [];
  activeSessionId.value = null;
}

export function useMainChatContext() {
  function setMessages(next: ChatMessage[], sessionId?: string | null): void {
    messages.value = next;
    if (sessionId !== undefined) {
      activeSessionId.value = sessionId;
    }
  }

  function clearMessages(): void {
    messages.value = [];
    activeSessionId.value = null;
  }

  function getFormattedContext(locale?: string): string {
    return formatMainChatContext(messages.value, { locale });
  }

  return {
    messages: readonly(messages),
    activeSessionId: readonly(activeSessionId),
    setMessages,
    clearMessages,
    getFormattedContext,
  };
}
