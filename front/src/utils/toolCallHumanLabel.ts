import { t } from './i18nT';

function formatManagedToolLabel(name: string): string {
  if (name.startsWith('managed__')) {
    const rest = name.slice('managed__'.length);
    const sep = rest.indexOf('__');
    if (sep > 0) {
      const connector = rest.slice(0, sep);
      const tool = rest.slice(sep + 2).replace(/_/g, ' ');
      return t('toolCalls.managedConnectorTool', { connector, tool });
    }
  }

  const legacyRest = name.slice('managed_'.length);
  const legacyParts = legacyRest.split('_');
  if (legacyParts.length <= 1) {
    return legacyParts[0] ?? legacyRest;
  }
  const connector = legacyParts[0] ?? '';
  const tool = legacyParts.slice(1).join(' ');
  return t('toolCalls.managedConnectorTool', { connector, tool });
}

/** Libellé lisible par défaut quand le sidecar n'envoie pas de humanSummary. */
export function fallbackHumanLabel(
  name: string,
  args?: Record<string, unknown>,
): string {
  if (name.startsWith('managed_')) {
    return formatManagedToolLabel(name);
  }

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
    case 'write_pptx':
      return t('toolCalls.writePptx');
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
