import { describe, expect, it } from 'vitest';
import { fallbackHumanLabel } from '@utils/toolCallHumanLabel';

describe('fallbackHumanLabel', () => {
  it('retourne un libellé lisible pour les outils connus', () => {
    expect(fallbackHumanLabel('read_documents')).toBe("J'ai lu des documents");
    expect(fallbackHumanLabel('generate_document')).toBe("J'ai créé un document");
    expect(fallbackHumanLabel('search_kb')).toBe("J'ai cherché dans la mémoire");
    expect(fallbackHumanLabel('web_search')).toBe('Recherche sur le web');
    expect(fallbackHumanLabel('list_files')).toBe("J'ai listé les fichiers");
    expect(fallbackHumanLabel('run_code')).toBe("J'ai exécuté un calcul");
  });

  it('retourne un libellé générique pour un outil inconnu', () => {
    expect(fallbackHumanLabel('unknown_tool')).toBe("J'ai effectué une action");
  });
});
