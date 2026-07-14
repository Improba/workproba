import { useQueryParams } from 'src/../lib-improba/composables/use-query-params';
import { useAuth } from 'src/../lib-improba/composables/use-auth';
import { useAppSettings } from '@composables/useAppSettings';
import type { QVueGlobals } from 'quasar';
import { Router } from 'vue-router';
import { applyUiTheme, resolveBootUiTheme } from '@utils/uiTheme';

// Init improba composables that need to be initialized at the start of the app
export const useImprobaInit = async (quasar: QVueGlobals, router: Router) => {
  // Init query params store
  const qp = useQueryParams(router);
  await qp.methods.initRouteQuery();

  // Cache localStorage puis settings Tauri avant le premier rendu.
  applyUiTheme(resolveBootUiTheme(), quasar);
  const { load, uiTheme } = useAppSettings();
  await load();
  applyUiTheme(uiTheme.value, quasar);

  // Auth init
  const auth = useAuth(router);
  await auth.methods.init();
};
