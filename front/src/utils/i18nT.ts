import { i18n } from '@boot/i18n';

type TranslateFn = (
  key: string,
  pluralOrValues?: number | Record<string, unknown>,
  values?: Record<string, unknown>,
) => string;

export function t(
  key: string,
  pluralOrValues?: number | Record<string, unknown>,
  values?: Record<string, unknown>,
): string {
  const translate = i18n().global.t as TranslateFn;
  if (typeof pluralOrValues === 'number') {
    return translate(key, pluralOrValues, values ?? {});
  }
  return translate(key, pluralOrValues ?? {});
}
