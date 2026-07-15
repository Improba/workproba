import { describe, expect, it } from 'vitest';
import {
  MISTRAL_BUILTIN_SET,
  OLLAMA_BUILTIN_SET,
  capabilityLabels,
  enrichSetFromBuiltin,
  providerSetToSidecar,
  sidecarSetToProviderSet,
} from '@utils/providerSets';

const t = (key: string) => {
  const labels: Record<string, string> = {
    'settings.engine.capabilityVision': 'Voit les images',
    'settings.engine.capabilityPdfScanned': 'Lit les PDF scannés',
    'settings.engine.capabilityMemory': 'A une mémoire',
    'settings.engine.capabilityReasoning': 'Réfléchit longuement',
    'settings.engine.capabilityTools': 'Utilise des outils',
    'settings.engine.capabilityWebSearch': 'Recherche sur le web',
  };
  return labels[key] ?? key;
};

describe('providerSets web_search capability', () => {
  it('expose web_search sur les sets intégrés Mistral et Ollama', () => {
    expect(MISTRAL_BUILTIN_SET.capabilities.webSearch).toBe(true);
    expect(OLLAMA_BUILTIN_SET.capabilities.webSearch).toBe(true);
  });

  it('affiche le libellé guidé sans jargon technique', () => {
    const labels = capabilityLabels(MISTRAL_BUILTIN_SET, 'guided', t);
    expect(labels).toContain('Recherche sur le web');
    expect(labels.some((label) => /tavily/i.test(label))).toBe(false);
  });

  it('round-trip sidecar préserve web_search', () => {
    const sidecar = providerSetToSidecar(MISTRAL_BUILTIN_SET);
    expect((sidecar.capabilities as Record<string, unknown>).web_search).toBe(true);
    const round = sidecarSetToProviderSet(sidecar);
    expect(round.capabilities.webSearch).toBe(true);
  });

  it('enrichit webSearch depuis le template builtin', () => {
    const stored = {
      ...MISTRAL_BUILTIN_SET,
      capabilities: { ...MISTRAL_BUILTIN_SET.capabilities, webSearch: false },
    };
    const enriched = enrichSetFromBuiltin(stored);
    expect(enriched.capabilities.webSearch).toBe(true);
  });
});
