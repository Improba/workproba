/**
 * Pont legacy Mastok → thème graphique Workproba.
 * Préférer useUiTheme() pour la persistance Tauri.
 */

import type { QVueGlobals } from 'quasar';
import type { UiThemeId } from '@utils/uiTheme';
import { applyUiTheme, uiThemeIsDark } from '@utils/uiTheme';

export const useTheme = (quasar: QVueGlobals) => {
  const methods = {
    /** @deprecated Utiliser useUiTheme().setUiTheme */
    setTheme(isDark: boolean) {
      const themeId: UiThemeId = isDark ? 'charcoal' : 'paper';
      applyUiTheme(themeId, quasar);
    },
    init() {
      // Persistance : useUiTheme + AppSettings (Tauri).
    },
  };

  return {
    state: {
      theme: quasar?.dark?.isActive ? 'dark' : 'light',
    },
    quasar,
    methods,
  };
};

export { uiThemeIsDark };
