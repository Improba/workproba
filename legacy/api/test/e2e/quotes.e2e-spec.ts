import { describe, expect, it, vi } from 'vitest';

import { QuoteController } from '@core/quotes/quote.controller';
import { QuoteService } from '@core/quotes/quote.service';

describe('Quotes (e2e support)', () => {
  it('retourne une citation via QuoteController', () => {
    const quoteServiceMock = {
      generateRandomQuote: vi.fn(() => ({
        quote: 'Les étoiles dansent dans un ciel infini.',
      })),
    } as unknown as QuoteService;

    const controller = new QuoteController(quoteServiceMock);
    const response = controller.getRandomQuote();

    expect(quoteServiceMock.generateRandomQuote).toHaveBeenCalledTimes(1);
    expect(response.quote).toContain('Les étoiles');
  });
});
