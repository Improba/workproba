import type { QVueGlobals } from 'quasar';

/** Identifiants de thèmes graphiques persistés (Tauri AppSettings.uiTheme). */
export type UiThemeId = 'paper' | 'charcoal';

export interface UiThemeDefinition {
  id: UiThemeId;
  colorScheme: 'light' | 'dark';
  /** Cible du toggle soleil/lune dans la title bar. */
  toggleTarget: UiThemeId;
}

export const UI_THEMES: Record<UiThemeId, UiThemeDefinition> = {
  paper: {
    id: 'paper',
    colorScheme: 'light',
    toggleTarget: 'charcoal',
  },
  charcoal: {
    id: 'charcoal',
    colorScheme: 'dark',
    toggleTarget: 'paper',
  },
};

export const UI_THEME_IDS = Object.keys(UI_THEMES) as UiThemeId[];

export const UI_THEME_STORAGE_KEY = 'workproba:uiTheme';

export function isUiThemeId(value: unknown): value is UiThemeId {
  return typeof value === 'string' && value in UI_THEMES;
}

/** Lecture synchrone du cache local (dernier thème persisté). */
export function readCachedUiTheme(): UiThemeId | null {
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem(UI_THEME_STORAGE_KEY);
  return isUiThemeId(raw) ? raw : null;
}

export function writeCachedUiTheme(themeId: UiThemeId): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(UI_THEME_STORAGE_KEY, themeId);
}

/** Fallback au premier lancement (settings absents) ou valeur invalide. */
export function resolveInitialUiTheme(stored?: UiThemeId | null): UiThemeId {
  if (stored && isUiThemeId(stored)) {
    return stored;
  }
  const envDefault = process.env.DEFAULT_COLOR_MODE;
  return envDefault === 'dark' ? 'charcoal' : 'paper';
}

/** Thème appliqué au boot, avant le round-trip Tauri (évite le flash). */
export function resolveBootUiTheme(): UiThemeId {
  return readCachedUiTheme() ?? resolveInitialUiTheme(null);
}

export function uiThemeToggleTarget(current: UiThemeId): UiThemeId {
  return UI_THEMES[current].toggleTarget;
}

export function uiThemeIsDark(themeId: UiThemeId): boolean {
  return UI_THEMES[themeId].colorScheme === 'dark';
}

/** Applique le thème graphique (Quasar dark + attributs DOM pour le shell / Shiki). */
export function applyUiTheme(themeId: UiThemeId, quasar?: QVueGlobals | null): void {
  const def = UI_THEMES[themeId];
  quasar?.dark?.set(def.colorScheme === 'dark');

  if (typeof document === 'undefined') {
    return;
  }

  document.documentElement.setAttribute('data-ui-theme', themeId);
  document.documentElement.setAttribute('data-theme', def.colorScheme);
}
