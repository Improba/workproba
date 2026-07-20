import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CloudDesktopAuthError,
  displayNameFromUsername,
  loginDesktopCloud,
} from '@services/cloudDesktopAuth';

describe('cloudDesktopAuth', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('retourne le token sur login réussi', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ token: 'jwt-abc' }),
      }),
    );

    const result = await loginDesktopCloud({
      baseUrl: 'http://localhost:3336/',
      username: 'alice@org.test',
      password: 'secret',
    });

    expect(result).toEqual({ token: 'jwt-abc' });
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:3336/devices/login',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ username: 'alice@org.test', password: 'secret' }),
      }),
    );
  });

  it('lève une erreur explicite sur 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({}),
      }),
    );

    await expect(
      loginDesktopCloud({
        baseUrl: 'http://localhost:3336',
        username: 'alice',
        password: 'bad',
      }),
    ).rejects.toMatchObject({
      message: 'cloud.loginInvalidCredentials',
      status: 401,
    } satisfies Partial<CloudDesktopAuthError>);
  });

  it('extrait le nom local depuis un e-mail', () => {
    expect(displayNameFromUsername('alice@org.test')).toBe('alice');
    expect(displayNameFromUsername('bob')).toBe('bob');
  });
});
