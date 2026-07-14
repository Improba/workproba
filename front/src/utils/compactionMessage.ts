/** Préfixes i18n du résumé de compaction (fr + en), alignés backend/front. */
export const COMPACTION_SUMMARY_PREFIXES = [
  'Résumé des échanges précédents :\n\n',
  'Résumé des échanges précédents :',
  'Summary of previous exchanges:\n\n',
  'Summary of previous exchanges:',
] as const;

export function isCompactionSummaryContent(content: string | null | undefined): boolean {
  if (!content) return false;
  const start = content.trimStart();
  return COMPACTION_SUMMARY_PREFIXES.some((prefix) => start.startsWith(prefix));
}

export function isCompactionMessageLike(
  role: string,
  content: string | null | undefined,
  messageKind?: string,
): boolean {
  if (messageKind === 'compaction') return true;
  if (!isCompactionSummaryContent(content)) return false;
  return role === 'user' || role === 'system';
}
