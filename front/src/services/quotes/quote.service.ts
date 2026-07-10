import { api } from 'boot/axios';

export interface IQuoteResponse {
  quote: string;
}

export const QuoteService = {
  /**
   * Récupère une phrase générée aléatoirement par le backend
   * @returns {Promise<IQuoteResponse>} La phrase générée
   */
  async getRandomQuote(): Promise<IQuoteResponse> {
    const response = await api().get('/quotes/random');
    return response.data;
  },
};

