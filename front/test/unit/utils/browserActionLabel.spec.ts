import { describe, expect, it } from 'vitest';
import { buildBrowserAiActionOverlay } from '@utils/browserActionLabel';

describe('browserActionLabel', () => {
  it('utilise human_summary quand présent', () => {
    const overlay = buildBrowserAiActionOverlay('browser_click', {
      human_summary: "J'ai cliqué sur l'élément e42",
    });
    expect(overlay?.label).toBe("J'ai cliqué sur l'élément e42");
  });

  it('retombe sur l’URL pour browser_navigate', () => {
    const overlay = buildBrowserAiActionOverlay('browser_navigate', {
      url: 'https://example.com/pricing',
    });
    expect(overlay?.label).toBe('https://example.com/pricing');
  });

  it('retombe sur un libellé générique pour browser_type', () => {
    const overlay = buildBrowserAiActionOverlay('browser_type', {});
    expect(overlay?.label).toBe('Type');
  });
});
