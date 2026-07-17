const SUBJECT_MAX_LEN = 100;
const DONE_SUBJECT_MAX_LEN = 120;
const SUMMARY_ITEM_MAX = 5;
const SUMMARY_LINE_MAX_LEN = 120;
const MIN_SIGNIFICANT_LEN = 3;

function normalizeNewlines(content: string): string {
  return content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function isSeparatorLine(line: string): boolean {
  const trimmed = line.trim();
  return /^[-*_]{3,}$/.test(trimmed);
}

function stripBulletPrefix(line: string): string {
  return line.replace(/^[\s>*•\-]+\s*/, '').trim();
}

function isSignificantLine(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed || isSeparatorLine(trimmed)) return false;
  const withoutBullet = stripBulletPrefix(trimmed);
  return withoutBullet.length >= MIN_SIGNIFICANT_LEN;
}

function truncate(text: string, max: number): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1).trimEnd()}…`;
}

function significantLines(content: string): string[] {
  return normalizeNewlines(content)
    .split('\n')
    .map((line) => line.trim())
    .filter(isSignificantLine)
    .map(stripBulletPrefix);
}

function lastSentence(text: string): string {
  const parts = text
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter((part) => part.length >= MIN_SIGNIFICANT_LEN);
  if (!parts.length) return text.trim();
  return parts[parts.length - 1]!;
}

function firstUsefulSentence(lines: string[]): string | null {
  for (const line of lines) {
    const first = line
      .split(/(?<=[.!?])\s+/)
      .map((part) => part.trim())
      .find((part) => part.length >= MIN_SIGNIFICANT_LEN);
    if (first) return first;
    if (line.length >= MIN_SIGNIFICANT_LEN) return line;
  }
  return null;
}

function pickDoneSubject(lines: string[]): string | null {
  if (!lines.length) return null;
  const first = firstUsefulSentence(lines);
  const lastLine = lines[lines.length - 1]!;
  const last = lastSentence(lastLine);
  if (!first) return truncate(last, DONE_SUBJECT_MAX_LEN);
  if (!last || first === last) return truncate(first, DONE_SUBJECT_MAX_LEN);
  return truncate(
    last.length > first.length ? last : first,
    DONE_SUBJECT_MAX_LEN,
  );
}

/** Sujet courant dérivé du contenu thinking (dernière ligne / phrase significative). */
export function deriveThinkingSubject(content: string): string | null {
  const lines = significantLines(content);
  if (!lines.length) return null;
  const lastLine = lines[lines.length - 1]!;
  const candidate = lastSentence(lastLine);
  if (candidate.length < MIN_SIGNIFICANT_LEN) return null;
  return truncate(candidate, SUBJECT_MAX_LEN);
}

/** Sujet figé en fin de thinking (première phrase utile ou dernière si plus informative). */
export function deriveThinkingSubjectDone(content: string): string | null {
  const lines = significantLines(content);
  return pickDoneSubject(lines);
}

/** Résumé prose (3 à 5 lignes / phrases significatives). */
export function deriveThinkingSummary(content: string): string | null {
  const lines = significantLines(content);
  if (!lines.length) return null;

  const items: string[] = [];
  for (const line of lines) {
    const sentences = line
      .split(/(?<=[.!?])\s+/)
      .map((part) => part.trim())
      .filter((part) => part.length >= MIN_SIGNIFICANT_LEN);
    if (sentences.length) {
      for (const sentence of sentences) {
        items.push(truncate(sentence, SUMMARY_LINE_MAX_LEN));
        if (items.length >= SUMMARY_ITEM_MAX) break;
      }
    } else {
      items.push(truncate(line, SUMMARY_LINE_MAX_LEN));
    }
    if (items.length >= SUMMARY_ITEM_MAX) break;
  }

  if (!items.length) return null;
  return items.join(' · ');
}
