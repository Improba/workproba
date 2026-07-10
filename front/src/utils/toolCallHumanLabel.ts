/** Libellé lisible par défaut quand le sidecar n'envoie pas de humanSummary. */
export function fallbackHumanLabel(
  name: string,
  _args?: Record<string, unknown>,
): string {
  switch (name) {
    case 'read_documents':
      return "J'ai lu des documents";
    case 'generate_document':
      return "J'ai créé un document";
    case 'search_kb':
      return "J'ai cherché dans la mémoire";
    case 'list_files':
      return "J'ai listé les fichiers";
    case 'run_code':
      return "J'ai exécuté un calcul";
    default:
      return "J'ai effectué une action";
  }
}
