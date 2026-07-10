import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UserService } from '../../../src/services/users/user.service';

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

describe('UserService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getCurrentUser appelle le bon endpoint', async () => {
    const payload = { id: 1, roles: ['admin'] };
    getMock.mockResolvedValue({ data: payload });

    await expect(UserService.getCurrentUser()).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith('/users/current');
  });

  it('updateCurrentUser appelle le bon endpoint avec son payload', async () => {
    const payload = { id: 1, firstname: 'Alexis' };
    patchMock.mockResolvedValue({ data: payload });
    const dto = { firstname: 'Alexis' } as never;

    await expect(UserService.updateCurrentUser(dto)).resolves.toEqual(payload);
    expect(patchMock).toHaveBeenCalledWith('/users/current', dto);
  });

  it('utilise bien le client api()', async () => {
    getMock.mockResolvedValue({ data: { id: 1 } });

    await UserService.getCurrentUser();

    expect(apiMock).toHaveBeenCalledTimes(1);
    expect(postMock).not.toHaveBeenCalled();
    expect(deleteMock).not.toHaveBeenCalled();
  });
});
