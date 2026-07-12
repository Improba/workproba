/** Titres backend / i18n considérés comme provisoires (renommables par LLM). */
const PROVISIONAL_TITLE_KEYS = [
  'chat.page.defaultTitle',
  'common.newConversation',
] as const;

const PROVISIONAL_TITLE_FALLBACKS = new Set([
  'Conversation',
  'Nouvelle conversation',
  'New conversation',
]);

export function isProvisionalConversationTitle(
  title: string,
  t: (key: string) => string,
): boolean {
  const trimmed = title.trim();
  if (!trimmed) return true;
  if (PROVISIONAL_TITLE_FALLBACKS.has(trimmed)) return true;
  return PROVISIONAL_TITLE_KEYS.some((key) => trimmed === t(key));
}
