import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QuoteService } from '../../../src/services/quotes/quote.service';

const {
  apiMock,
  getMock,
  postMock,
  patchMock,
  deleteMock,
} = vi.hoisted(() => {
  const get = vi.fn();
  const post = vi.fn();
  const patch = vi.fn();
  const del = vi.fn();

  return {
    apiMock: vi.fn(() => ({ get, post, patch, delete: del })),
    getMock: get,
    postMock: post,
    patchMock: patch,
    deleteMock: del,
  };
});

vi.mock('boot/axios', () => ({
  api: apiMock,
}));

describe('QuoteService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('récupère une citation aléatoire via le bon endpoint', async () => {
    const payload = { quote: 'Stay curious' };
    getMock.mockResolvedValue({ data: payload });

    await expect(QuoteService.getRandomQuote()).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith('/quotes/random');
  });

  it('utilise bien le client api()', async () => {
    getMock.mockResolvedValue({ data: { quote: 'ok' } });

    await QuoteService.getRandomQuote();

    expect(apiMock).toHaveBeenCalledTimes(1);
    expect(postMock).not.toHaveBeenCalled();
    expect(patchMock).not.toHaveBeenCalled();
    expect(deleteMock).not.toHaveBeenCalled();
  });
});
