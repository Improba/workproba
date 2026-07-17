import { describe, expect, it } from 'vitest';
import { fallbackHumanLabel } from '@utils/toolCallHumanLabel';

describe('fallbackHumanLabel', () => {
  it('retourne un libellé lisible pour les outils connus', () => {
    expect(fallbackHumanLabel('read_documents')).toBe("J'ai lu des documents");
    expect(fallbackHumanLabel('read_document')).toBe("J'ai lu des documents");
    expect(fallbackHumanLabel('generate_document')).toBe("J'ai créé un document");
    expect(fallbackHumanLabel('write_docx')).toBe("J'ai créé un document Word");
    expect(fallbackHumanLabel('write_xlsx')).toBe("J'ai créé un classeur Excel");
    expect(fallbackHumanLabel('write_pdf')).toBe("J'ai créé un PDF");
    expect(fallbackHumanLabel('publish_artifact')).toBe("J'ai publié un document dans un projet");
    expect(fallbackHumanLabel('create_project')).toBe("J'ai créé un projet");
    expect(fallbackHumanLabel('list_projects')).toBe("J'ai listé les projets");
    expect(fallbackHumanLabel('sync_to_cloud')).toBe("J'ai synchronisé des documents vers le cloud");
    expect(fallbackHumanLabel('sync_from_cloud')).toBe("J'ai récupéré des documents depuis le cloud");
    expect(fallbackHumanLabel('enroll_to_cloud')).toBe("J'ai connecté ce poste au cloud");
    expect(fallbackHumanLabel('sync_managed_regards')).toBe("J'ai synchronisé les regards de l'organisation");
    expect(fallbackHumanLabel('invoke_managed_connector')).toBe("J'ai appelé un connecteur Improba Cloud");
    expect(
      fallbackHumanLabel('invoke_managed_connector', { connector_id: 'echo' }),
    ).toBe("J'ai appelé le connecteur echo");
    expect(fallbackHumanLabel('search_kb')).toBe("J'ai cherché dans la mémoire");
    expect(fallbackHumanLabel('web_search')).toBe('Recherche sur le web');
    expect(fallbackHumanLabel('list_files')).toBe("J'ai listé les fichiers");
    expect(fallbackHumanLabel('run_code')).toBe("J'ai exécuté un calcul");
  });

  it('retourne un libellé générique pour un outil inconnu', () => {
    expect(fallbackHumanLabel('unknown_tool')).toBe("J'ai effectué une action");
  });
});
