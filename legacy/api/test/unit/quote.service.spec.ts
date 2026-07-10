import { QuoteService } from '@core/quotes/quote.service';

describe('QuoteService', () => {
  let service: QuoteService;

  beforeEach(() => {
    service = new QuoteService();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('generateRandomQuote', () => {
    it('should return a quote string', () => {
      const result = service.generateRandomQuote();

      expect(result.quote).toBeDefined();
      expect(typeof result.quote).toBe('string');
      expect(result.quote.length).toBeGreaterThan(0);
      expect(result.quote.endsWith('.')).toBe(true);
    });

    it('should produce different structures over multiple calls', () => {
      const quotes = new Set(
        Array.from({ length: 20 }, () => service.generateRandomQuote().quote),
      );

      expect(quotes.size).toBeGreaterThan(1);
    });
  });
});
