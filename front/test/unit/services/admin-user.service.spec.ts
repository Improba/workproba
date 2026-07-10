import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminUserService } from '../../../src/services/users/admin/admin-user.service';

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

describe('AdminUserService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('paginate envoie les paramètres dans query params', async () => {
    const payload = { count: 1, results: [{ id: 1 }] };
    getMock.mockResolvedValue({ data: payload });
    const params = {
      limit: 10,
      offset: 0,
      orderBy: 'createdAt',
      order: 'DESC',
    } as never;

    await expect(AdminUserService.paginate(params)).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith('/users-admin/paginate', { params });
  });

  it('create envoie le dto au bon endpoint', async () => {
    const payload = { id: 2 };
    postMock.mockResolvedValue({ data: payload });
    const dto = { firstname: 'New', lastname: 'Admin' } as never;

    await expect(AdminUserService.create(dto)).resolves.toEqual(payload);
    expect(postMock).toHaveBeenCalledWith('/users-admin', dto);
  });

  it('update envoie le dto au bon endpoint', async () => {
    const payload = { id: 2, firstname: 'Updated' };
    patchMock.mockResolvedValue({ data: payload });
    const dto = { id: 2, firstname: 'Updated' } as never;

    await expect(AdminUserService.update(dto)).resolves.toEqual(payload);
    expect(patchMock).toHaveBeenCalledWith('/users-admin', dto);
  });

  it('findOne récupère un utilisateur par id', async () => {
    const payload = { id: 7 };
    getMock.mockResolvedValue({ data: payload });

    await expect(AdminUserService.findOne(7)).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith('/users-admin/7');
  });

  it('delete supprime un utilisateur par id', async () => {
    const payload = { id: 9 };
    deleteMock.mockResolvedValue({ data: payload });

    await expect(AdminUserService.delete(9)).resolves.toEqual(payload);
    expect(deleteMock).toHaveBeenCalledWith('/users-admin/9');
  });

  it('utilise bien le client api()', async () => {
    getMock.mockResolvedValue({ data: { id: 1 } });

    await AdminUserService.findOne(1);

    expect(apiMock).toHaveBeenCalledTimes(1);
  });
});
