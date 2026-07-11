import { createI18n, type I18n } from 'vue-i18n';
import { App, getCurrentInstance } from 'vue';
import messages from 'src/i18n';

export type MessageLanguages = keyof typeof messages;
export type MessageSchema = (typeof messages)['en-US'];
export type AppLocale = 'fr' | 'en-US';

export const LOCALE_STORAGE_KEY = 'workproba:locale';

declare module 'vue-i18n' {
  export interface DefineLocaleMessage extends MessageSchema {}
  export interface DefineDateTimeFormat {}
  export interface DefineNumberFormat {}
}

let i18nInstance: I18n | null = null;

function readStoredLocale(): AppLocale | null {
  if (typeof localStorage === 'undefined') return null;
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
  return normalizeLocale(stored);
}

/** Détecte la locale OS (navigator ou Tauri) et retourne fr ou en-US. */
export function detectOsLocale(): AppLocale {
  if (typeof navigator !== 'undefined' && navigator.language) {
    return normalizeLocale(navigator.language) ?? 'fr';
  }
  return 'fr';
}

export function normalizeLocale(value: string | null | undefined): AppLocale | null {
  if (!value) return null;
  const lower = value.toLowerCase();
  if (lower.startsWith('en')) return 'en-US';
  if (lower.startsWith('fr')) return 'fr';
  return null;
}

export function resolveInitialLocale(): AppLocale {
  return readStoredLocale() ?? detectOsLocale();
}

/** Locale envoyée au sidecar (fr | en). */
export function toSidecarLocale(locale: string): 'fr' | 'en' {
  return locale.startsWith('en') ? 'en' : 'fr';
}

export function setLang(locale: string): void {
  const resolved = normalizeLocale(locale) ?? 'fr';
  if (i18nInstance) {
    i18nInstance.global.locale.value = resolved;
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(LOCALE_STORAGE_KEY, resolved);
  }
}

export const boot = (options: { app: App<any> }) => {
  const initialLocale = resolveInitialLocale();
  const i18n = createI18n({
    locale: initialLocale,
    fallbackLocale: 'fr',
    legacy: false,
    messages,
    globalInjection: true,
  });

  i18nInstance = i18n;
  options.app.use(i18n);
  options.app.config.globalProperties.$i18n_ = i18n;
};

export const i18n = (): I18n => {
  if (i18nInstance) return i18nInstance;

  const instance = getCurrentInstance();
  const fromApp = instance?.appContext.config.globalProperties.$i18n_ as
    | I18n
    | undefined;
  if (fromApp) {
    i18nInstance = fromApp;
    return fromApp;
  }

  throw new Error('boot/i18n: _i18n not initialized');
};
