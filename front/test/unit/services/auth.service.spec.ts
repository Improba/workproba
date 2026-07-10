import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthService } from '../../../src/services/users/auth.service';

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

describe('AuthService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('login envoie le dto au bon endpoint', async () => {
    const payload = { token: 'jwt-login' };
    postMock.mockResolvedValue({ data: payload });

    const dto = {
      username: 'admin@test.local',
      password: 'secret',
    } as never;

    await expect(AuthService.login(dto)).resolves.toEqual(payload);
    expect(postMock).toHaveBeenCalledWith('/auth-jwt/login', dto);
  });

  it('refreshToken envoie le token au bon endpoint', async () => {
    const payload = { token: 'jwt-refresh' };
    postMock.mockResolvedValue({ data: payload });

    await expect(AuthService.refreshToken('old-token')).resolves.toEqual(payload);
    expect(postMock).toHaveBeenCalledWith('/auth-jwt/refreshToken', {
      token: 'old-token',
    });
  });

  it('register envoie le dto au bon endpoint', async () => {
    const payload = { token: 'jwt-register' };
    postMock.mockResolvedValue({ data: payload });

    const dto = {
      username: 'new@test.local',
      password: 'secret',
      firstname: 'New',
      lastname: 'User',
    } as never;

    await expect(AuthService.register(dto)).resolves.toEqual(payload);
    expect(postMock).toHaveBeenCalledWith('/auth-jwt/register', dto);
  });

  it('forgotPassword envoie le dto au bon endpoint', async () => {
    const payload = { sent: true };
    postMock.mockResolvedValue({ data: payload });

    const dto = { email: 'user@test.local' } as never;

    await expect(AuthService.forgotPassword(dto)).resolves.toEqual(payload);
    expect(postMock).toHaveBeenCalledWith('/auth-jwt/forgot-password', dto);
  });

  it('resetPassword envoie le dto au bon endpoint', async () => {
    const payload = { token: 'jwt-reset' };
    postMock.mockResolvedValue({ data: payload });

    const dto = {
      token: 'reset-token',
      password: 'new-secret',
    } as never;

    await expect(AuthService.resetPassword(dto)).resolves.toEqual(payload);
    expect(postMock).toHaveBeenCalledWith('/auth-jwt/reset-password', dto);
  });

  it('utilise bien le client api()', async () => {
    postMock.mockResolvedValue({ data: { token: 'jwt' } });

    await AuthService.login({ username: 'u', password: 'p' } as never);

    expect(apiMock).toHaveBeenCalledTimes(1);
    expect(getMock).not.toHaveBeenCalled();
    expect(patchMock).not.toHaveBeenCalled();
    expect(deleteMock).not.toHaveBeenCalled();
  });
});
