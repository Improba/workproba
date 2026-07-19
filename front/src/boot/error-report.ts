import { boot } from 'quasar/wrappers';
import { useErrorReport } from '@composables/useErrorReport';

export default boot(({ app }) => {
  const { openFromUnknown } = useErrorReport();

  app.config.errorHandler = (err, _instance, info) => {
    console.error('[vue]', err, info);
    openFromUnknown(err, 'ui');
  };

  window.addEventListener('unhandledrejection', (ev) => {
    console.error('[unhandledrejection]', ev.reason);
    openFromUnknown(ev.reason, 'ui');
  });
});
