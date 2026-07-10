export function estimateTokens(text: string): number {
  if (!text || !text.trim()) return 0;
  return Math.ceil(text.length / 4);
}

export function estimateMessagesTokens(messages: { content: string; role?: string }[]): number {
  return messages.reduce((sum, msg) => {
    const content = msg.content;
    if (content == null) return sum;
    return sum + estimateTokens(content);
  }, 0);
}
