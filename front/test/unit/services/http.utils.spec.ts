import { describe, expect, it, vi } from 'vitest';
import HttpUtils from '../../../src/services/utils/http.utils';

describe('HttpUtils.apiUrl', () => {
  it('retourne API_URL depuis les variables d’environnement quand disponible', () => {
    vi.stubEnv('API_URL', 'https://api.from.env');

    expect(HttpUtils.apiUrl()).toBe('https://api.from.env');
  });

  it('retourne window.__API_URL quand API_URL est absent et hors worker', () => {
    vi.stubEnv('API_URL', '');
    (self as any).__IS_WORKER = false;
    (window as any).__API_URL = 'https://api.from.window';

    expect(HttpUtils.apiUrl()).toBe('https://api.from.window');
  });

  it('retourne self.__API_URL quand exécuté dans un worker', () => {
    vi.stubEnv('API_URL', '');
    (self as any).__IS_WORKER = true;
    (self as any).__API_URL = 'https://api.from.worker';

    expect(HttpUtils.apiUrl()).toBe('https://api.from.worker');
  });
});
