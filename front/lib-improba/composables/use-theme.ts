/**
 * This composable is used to define the theme for the application.
 * It is used to validate the input values and to display the error messages.
 * 
 * Use case:
 * ```html
 * <template>
 *   <p>
 *     Theme is: {{ theme.state.theme }}
 *   </p>
 * </template>
 * 
 * <script lang="ts">
 * import { useTheme } from 'src/lib-improba/composables/use-theme';
 * 
 * export default defineComponent({
 *   setup() {
 *     // This will return the theme object with the theme for the application
 *     const theme = useTheme();
 * 
 *     // Usage
 *     theme.methods.setTheme(true);
 * 
 *     return { theme };
 *   },
 * });
 * </script>
 * ```
 */

import { defineComponent, reactive, watch, onMounted } from 'vue';
import { QVueGlobals } from 'quasar';

export const useTheme = (quasar: QVueGlobals) => {
  const state = reactive({
    theme: quasar?.dark?.isActive ? 'dark' : 'light',
    user: {} as any,
  });

  const methods = {
    init() {
      try {
        // const user = await UserService.getCurrentUser();
        // state.user = user;
        // methods.setTheme(state.user.preferDarkTheme);
      } catch (err) {
        // methods.setTheme(true, false);
      }
    },
    setTheme(isDark: boolean, updateUser = true) {
      quasar.dark.set(isDark);
      if (updateUser && state.user) {
        if (state.user.preferDarkTheme === isDark) return;

        state.user.preferDarkTheme = isDark;
        try {
          /*await UserService.updateCurrentUser({
            id: state.user.id,
            preferDarkTheme: state.user.preferDarkTheme,
          });
          await store.dispatch('auth/getTokenFromCookie');*/
        } catch (e: any) {
          // Persistance du thème côté serveur désactivée : rien à faire ici.
        }
      }
    },
  };

  return {
    state,
    quasar,
    methods,
  };
};
