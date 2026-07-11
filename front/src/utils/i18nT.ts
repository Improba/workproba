import { i18n } from '@boot/i18n';

export function t(
  key: string,
  pluralOrValues?: number | Record<string, unknown>,
  values?: Record<string, unknown>,
): string {
  const inst = i18n().global;
  if (typeof pluralOrValues === 'number') {
    return inst.t(key, pluralOrValues, values ?? {});
  }
  return inst.t(key, pluralOrValues ?? {});
}
