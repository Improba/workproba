import { computed, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useAppSettings } from '@composables/useAppSettings';
import type { UiThemeId } from '@utils/uiTheme';
import {
  applyUiTheme,
  uiThemeIsDark,
  uiThemeToggleTarget,
} from '@utils/uiTheme';

let themeWatchStarted = false;

/** Réinitialise le watcher singleton (tests uniquement). */
export function resetUiThemeWatchForTests(): void {
  themeWatchStarted = false;
}

export function useUiTheme() {
  const quasar = useQuasar();
  const { uiTheme, loaded, setUiTheme: persistUiTheme } = useAppSettings();

  const isDark = computed(() => uiThemeIsDark(uiTheme.value));

  if (!themeWatchStarted) {
    themeWatchStarted = true;
    watch(
      [uiTheme, loaded],
      ([themeId, isLoaded]) => {
        if (!isLoaded) return;
        applyUiTheme(themeId, quasar);
      },
      { immediate: true },
    );
  }

  async function setUiTheme(themeId: UiThemeId): Promise<void> {
    await persistUiTheme(themeId);
  }

  async function toggleUiTheme(): Promise<void> {
    await setUiTheme(uiThemeToggleTarget(uiTheme.value));
  }

  return {
    uiTheme,
    isDark,
    loaded,
    setUiTheme,
    toggleUiTheme,
  };
}
