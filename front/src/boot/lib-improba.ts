import { boot } from 'quasar/wrappers';
import { boot as bootGlobalComponent } from 'src/../lib-improba/boot/global-components';
import { boot as bootI18n } from 'src/../lib-improba/boot/i18n';
import { useImprobaInit } from 'src/../lib-improba/composables/use-improba-init';

export default boot(async ({ app, router }) => {
  bootI18n({ app });
  bootGlobalComponent({ app });

  const quasar = app.config.globalProperties.$q;

  // Init improba composables that need to be initialized at the start of the app
  await useImprobaInit(quasar, router);
});
