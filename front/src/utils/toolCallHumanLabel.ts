import { t } from './i18nT';

/** Libellé lisible par défaut quand le sidecar n'envoie pas de humanSummary. */
export function fallbackHumanLabel(
  name: string,
  _args?: Record<string, unknown>,
): string {
  switch (name) {
    case 'read_documents':
      return t('toolCalls.readDocuments');
    case 'generate_document':
      return t('toolCalls.generateDocument');
    case 'search_kb':
      return t('toolCalls.searchKb');
    case 'list_files':
      return t('toolCalls.listFiles');
    case 'run_code':
      return t('toolCalls.runCode');
    default:
      return t('toolCalls.defaultAction');
  }
}
