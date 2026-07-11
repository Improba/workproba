import { describe, expect, it } from 'vitest';
import fr from 'src/i18n/fr';
import enUS from 'src/i18n/en-US';

function flattenKeys(
  obj: Record<string, unknown>,
  prefix = '',
): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenKeys(value as Record<string, unknown>, path);
    }
    return [path];
  });
}

describe('i18n locales parity', () => {
  it('fr et en-US partagent les mêmes clés', () => {
    const frKeys = new Set(flattenKeys(fr as Record<string, unknown>));
    const enKeys = new Set(flattenKeys(enUS as Record<string, unknown>));

    const missingInEn = [...frKeys].filter((key) => !enKeys.has(key));
    const missingInFr = [...enKeys].filter((key) => !frKeys.has(key));

    expect(missingInEn, `clés absentes en en-US: ${missingInEn.join(', ')}`).toEqual([]);
    expect(missingInFr, `clés absentes en fr: ${missingInFr.join(', ')}`).toEqual([]);
  });
});
