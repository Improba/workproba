import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { QVueGlobals } from 'quasar';
import {
  UI_THEME_STORAGE_KEY,
  applyUiTheme,
  readCachedUiTheme,
  resolveBootUiTheme,
  resolveInitialUiTheme,
  uiThemeIsDark,
  uiThemeToggleTarget,
  writeCachedUiTheme,
} from '@utils/uiTheme';

describe('uiTheme', () => {
  beforeEach(() => {
    localStorage.removeItem(UI_THEME_STORAGE_KEY);
    document.documentElement.removeAttribute('data-ui-theme');
    document.documentElement.removeAttribute('data-theme');
  });

  it('resolveInitialUiTheme retourne paper par défaut', () => {
    expect(resolveInitialUiTheme(null)).toBe('paper');
    expect(resolveInitialUiTheme(undefined)).toBe('paper');
  });

  it('resolveInitialUiTheme conserve une valeur valide', () => {
    expect(resolveInitialUiTheme('charcoal')).toBe('charcoal');
  });

  it('resolveInitialUiTheme ignore une valeur inconnue', () => {
    expect(resolveInitialUiTheme('royal' as 'paper')).toBe('paper');
  });

  it('resolveBootUiTheme lit le cache localStorage', () => {
    writeCachedUiTheme('charcoal');
    expect(resolveBootUiTheme()).toBe('charcoal');
    expect(readCachedUiTheme()).toBe('charcoal');
  });

  it('readCachedUiTheme ignore une valeur invalide', () => {
    localStorage.setItem(UI_THEME_STORAGE_KEY, 'royal');
    expect(readCachedUiTheme()).toBeNull();
    expect(resolveBootUiTheme()).toBe('paper');
  });

  it('toggle paper ↔ charcoal', () => {
    expect(uiThemeToggleTarget('paper')).toBe('charcoal');
    expect(uiThemeToggleTarget('charcoal')).toBe('paper');
  });

  it('uiThemeIsDark reflète le colorScheme', () => {
    expect(uiThemeIsDark('paper')).toBe(false);
    expect(uiThemeIsDark('charcoal')).toBe(true);
  });

  it('applyUiTheme pose data-ui-theme et data-theme', () => {
    const darkSet = vi.fn();
    const quasar = { dark: { set: darkSet } } as unknown as QVueGlobals;

    applyUiTheme('charcoal', quasar);
    expect(document.documentElement.getAttribute('data-ui-theme')).toBe('charcoal');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(darkSet).toHaveBeenCalledWith(true);

    applyUiTheme('paper', quasar);
    expect(document.documentElement.getAttribute('data-ui-theme')).toBe('paper');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(darkSet).toHaveBeenCalledWith(false);
  });
});
