export function estimateTokens(text: string): number {
  if (!text || !text.trim()) return 0;
  return Math.ceil(text.length / 4);
}

const ROLE_OVERHEAD_CHARS = 4;

export function estimateMessagesTokens(
  messages: {
    content: string;
    role?: string;
    thinking?: string | null;
    toolCalls?: Array<{ args?: Record<string, unknown>; result?: unknown }>;
  }[],
): number {
  return messages.reduce((sum, msg) => {
    let chars = ROLE_OVERHEAD_CHARS;
    if (msg.content != null) chars += msg.content.length;
    if (msg.thinking) chars += msg.thinking.length;
    for (const tc of msg.toolCalls ?? []) {
      try {
        chars += JSON.stringify(tc.args ?? {}).length;
        if (tc.result !== undefined) {
          chars += JSON.stringify(tc.result).length;
        }
      } catch {
        /* ignore non-serializable tool payloads */
      }
    }
    return sum + Math.ceil(chars / 4);
  }, 0);
}
