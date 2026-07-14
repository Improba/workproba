import { describe, expect, it } from 'vitest';
import {
  isCompactionMessageLike,
  isCompactionSummaryContent,
} from '@utils/compactionMessage';

describe('compactionMessage', () => {
  it('détecte le préfixe fr et en', () => {
    expect(
      isCompactionSummaryContent('Résumé des échanges précédents :\n\nContenu'),
    ).toBe(true);
    expect(
      isCompactionSummaryContent('Summary of previous exchanges:\n\nContent'),
    ).toBe(true);
    expect(isCompactionSummaryContent('Bonjour')).toBe(false);
  });

  it('identifie un message user sans messageKind explicite', () => {
    expect(
      isCompactionMessageLike(
        'user',
        'Résumé des échanges précédents :\n\nRésumé',
      ),
    ).toBe(true);
  });

  it('identifie le legacy system', () => {
    expect(
      isCompactionMessageLike(
        'system',
        'Summary of previous exchanges:\n\nSummary',
      ),
    ).toBe(true);
  });

  it('ignore un message system sans préfixe compaction', () => {
    expect(isCompactionMessageLike('system', 'Tu es un assistant.')).toBe(false);
  });
});
