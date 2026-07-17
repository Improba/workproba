import { t } from './i18nT';

/** Libellé lisible par défaut quand le sidecar n'envoie pas de humanSummary. */
export function fallbackHumanLabel(
  name: string,
  args?: Record<string, unknown>,
): string {
  switch (name) {
    case 'read_documents':
    case 'read_document':
      return t('toolCalls.readDocuments');
    case 'generate_document':
      return t('toolCalls.generateDocument');
    case 'write_docx':
      return t('toolCalls.writeDocx');
    case 'write_xlsx':
      return t('toolCalls.writeXlsx');
    case 'write_pdf':
      return t('toolCalls.writePdf');
    case 'publish_artifact':
      return t('toolCalls.publishArtifact');
    case 'create_project':
      return t('toolCalls.createProject');
    case 'list_projects':
      return t('toolCalls.listProjects');
    case 'sync_to_cloud':
      return t('toolCalls.syncToCloud');
    case 'sync_from_cloud':
      return t('toolCalls.syncFromCloud');
    case 'enroll_to_cloud':
      return t('toolCalls.enrollToCloud');
    case 'sync_managed_regards':
      return t('toolCalls.syncManagedRegards');
    case 'invoke_managed_connector': {
      const connectorId = args?.connector_id;
      if (typeof connectorId === 'string' && connectorId.trim()) {
        return t('toolCalls.invokeManagedConnectorNamed', { name: connectorId.trim() });
      }
      return t('toolCalls.invokeManagedConnector');
    }
    case 'search_kb':
      return t('toolCalls.searchKb');
    case 'web_search':
      return t('toolCalls.webSearchGeneric');
    case 'list_files':
      return t('toolCalls.listFiles');
    case 'run_code':
      return t('toolCalls.runCode');
    default:
      return t('toolCalls.defaultAction');
  }
}
