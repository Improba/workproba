import { describe, expect, it } from 'vitest';

import enUS from '../../../src/i18n/en-US/index';
import fr from '../../../src/i18n/fr/index';

type MessageTree = Record<string, unknown>;

type JargonViolation = {
  locale: 'fr' | 'en-US';
  key: string;
  value: string;
  term: string;
};

/** Namespaces user-facing en mode guidé (hors mode avancé). */
const GUIDED_TOP_LEVEL_NAMESPACES = ['chat', 'shell', 'common'] as const;

/** Clés techniques exclues du contrôle jargon. */
const EXCLUDED_KEY_PREFIXES = ['advanced.', 'errors.technical.', 'settings.advanced.'] as const;

function isGuidedKey(key: string): boolean {
  if (EXCLUDED_KEY_PREFIXES.some((prefix) => key.startsWith(prefix))) {
    return false;
  }

  const topLevel = key.split('.')[0];
  if (GUIDED_TOP_LEVEL_NAMESPACES.includes(topLevel as (typeof GUIDED_TOP_LEVEL_NAMESPACES)[number])) {
    return true;
  }

  // settings.* sauf clés advanced* (mode avancé)
  if (key.startsWith('settings.')) {
    const subKey = key.slice('settings.'.length);
    return !subKey.startsWith('advanced');
  }

  return false;
}

const JARGON_PATTERNS: ReadonlyArray<{ term: string; pattern: RegExp }> = [
  { term: 'provider set', pattern: /\bprovider\s+set\b/i },
  { term: 'provider', pattern: /\bprovider\b/i },
  { term: 'embeddings', pattern: /\bembeddings\b/i },
  { term: 'OCR-isée', pattern: /\bocr-is[ée]e\b/i },
  { term: 'OCR', pattern: /\bocr\b/i },
  { term: 'workspace', pattern: /\bworkspace\b/i },
  { term: 'sandbox', pattern: /\bsandbox\b/i },
  { term: 'artefact', pattern: /\bartefact\b/i },
  { term: 'API key', pattern: /\bapi\s+key\b/i },
  { term: 'set', pattern: /\bset\b/i },
];

function flattenMessages(
  messages: MessageTree,
  prefix = '',
): Record<string, string> {
  const flat: Record<string, string> = {};

  for (const [key, value] of Object.entries(messages)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;

    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(flat, flattenMessages(value as MessageTree, fullKey));
      continue;
    }

    if (typeof value === 'string') {
      flat[fullKey] = value;
    }
  }

  return flat;
}

function isCatalogEmpty(catalog: MessageTree): boolean {
  return Object.keys(flattenMessages(catalog)).length === 0;
}

function detectJargon(value: string): string | null {
  for (const { term, pattern } of JARGON_PATTERNS) {
    if (pattern.test(value)) {
      return term;
    }
  }

  return null;
}

function collectViolations(
  locale: JargonViolation['locale'],
  catalog: MessageTree,
): JargonViolation[] {
  const violations: JargonViolation[] = [];

  for (const [key, value] of Object.entries(flattenMessages(catalog))) {
    if (!isGuidedKey(key)) {
      continue;
    }

    const term = detectJargon(value);
    if (term) {
      violations.push({ locale, key, value, term });
    }
  }

  return violations.sort((a, b) =>
    a.locale.localeCompare(b.locale) ||
    a.key.localeCompare(b.key) ||
    a.term.localeCompare(b.term),
  );
}

describe('i18n jargon blacklist (mode guidé)', () => {
  it('ne contient aucun terme de la liste noire dans les namespaces guidés', () => {
    const catalogsEmpty = isCatalogEmpty(fr) && isCatalogEmpty(enUS);

    if (catalogsEmpty) {
      console.warn(
        '[jargon-blacklist] Catalogues i18n vides — test ignoré (en attente extraction T-V2-2).',
      );
      return;
    }

    const violations = [
      ...collectViolations('fr', fr),
      ...collectViolations('en-US', enUS),
    ];

    expect(violations).toMatchSnapshot();
    expect(violations).toEqual([]);
  });
});
