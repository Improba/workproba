import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpException, NotFoundException } from '@nestjs/common';

const { axiosPostMock } = vi.hoisted(() => ({
  axiosPostMock: vi.fn(),
}));

vi.mock('axios', () => ({
  default: {
    post: axiosPostMock,
  },
}));

import * as fs from 'node:fs';

import { BaseService } from '@lib-improba/base/base.service';
import {
  AdminUserController,
  PaginateUserDTO,
  UserCreateForAdminDto,
} from '@core/users/controllers/admin/admin-user.controller';
import { ExportService } from '@lib-improba/modules/exports/services/index.service';
import { QuoteService } from '@core/quotes/quote.service';
import { UserRoleEnum } from '@core/users/entities/user.entity';
import { UserService } from '@core/users/services/user.service';

describe('Services coverage (e2e support)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('couvre BaseService avec un repository mocké', async () => {
    const repository = {
      findOne: vi.fn(async (where) => ({ id: 1, where })),
      findOneById: vi.fn(async (id) => ({ id })),
      findAll: vi.fn(async () => [{ id: 2 }]),
      softDelete: vi.fn(async (id) => ({ id, deleted: true })),
    };

    const service = new BaseService<any, any>(repository);

    await expect(service.findOne({ id: 1 })).resolves.toEqual({
      id: 1,
      where: { id: 1 },
    });
    await expect(service.findOneById(1)).resolves.toEqual({ id: 1 });
    await expect(service.findAll()).resolves.toEqual([{ id: 2 }]);
    await expect(service.delete(2)).resolves.toEqual({ id: 2, deleted: true });

    expect(repository.findAll).toHaveBeenCalledWith({
      orderBy: { id: 'DESC' },
    });
  });

  it('couvre QuoteService pour chaque structure de phrase', () => {
    const service = new QuoteService();

    const randomSpy = vi
      .spyOn(Math, 'random')
      .mockReturnValueOnce(0.0)
      .mockReturnValue(0.0);
    const structure0 = service.generateRandomQuote();
    expect(structure0.quote.endsWith('.')).toBe(true);
    randomSpy.mockRestore();

    const randomSpy1 = vi
      .spyOn(Math, 'random')
      .mockReturnValueOnce(0.3)
      .mockReturnValue(0.1);
    const structure1 = service.generateRandomQuote();
    expect(structure1.quote.endsWith('.')).toBe(true);
    randomSpy1.mockRestore();

    const randomSpy2 = vi
      .spyOn(Math, 'random')
      .mockReturnValueOnce(0.6)
      .mockReturnValue(0.2);
    const structure2 = service.generateRandomQuote();
    expect(structure2.quote[0]).toBe(structure2.quote[0].toUpperCase());
    randomSpy2.mockRestore();

    const randomSpy3 = vi
      .spyOn(Math, 'random')
      .mockReturnValueOnce(0.9)
      .mockReturnValue(0.3);
    const structure3 = service.generateRandomQuote();
    expect(structure3.quote.endsWith('.')).toBe(true);
    randomSpy3.mockRestore();
  });

  it('couvre ExportService.toDocx et toPdf avec et sans outputPath', async () => {
    const service = new ExportService();
    const writeFileSpy = vi
      .spyOn(fs.promises, 'writeFile')
      .mockResolvedValue(undefined);

    axiosPostMock.mockResolvedValueOnce({ data: Buffer.from('docx-binary') });
    const docxRaw = await service.toDocx({
      html: '<p>Hello {{name}}</p>',
      variables: { name: 'Alice' },
    });
    expect(axiosPostMock).toHaveBeenCalledWith(
      expect.stringContaining('pandoc'),
      '<p>Hello Alice</p>',
      expect.objectContaining({
        responseType: 'stream',
      }),
    );
    expect(docxRaw).toEqual(Buffer.from('docx-binary'));

    axiosPostMock.mockResolvedValueOnce({ data: Buffer.from('docx-file') });
    const docxPath = await service.toDocx({
      html: '<p>File {{name}}</p>',
      variables: { name: 'Bob' },
      outputPath: '/tmp/out.docx',
    });
    expect(docxPath).toBe('/tmp/out.docx');
    expect(writeFileSpy).toHaveBeenCalledWith('/tmp/out.docx', Buffer.from('docx-file'));

    axiosPostMock.mockResolvedValueOnce({ data: Buffer.from('pdf-binary') });
    const pdfRaw = await service.toPdf({
      html: '<p>Pdf {{name}}</p>',
      variables: { name: 'Charly' },
    });
    expect(pdfRaw).toEqual(Buffer.from('pdf-binary'));

    axiosPostMock.mockResolvedValueOnce({ data: Buffer.from('pdf-file') });
    const pdfPath = await service.toPdf({
      html: '<p>Pdf file {{name}}</p>',
      variables: { name: 'Dora' },
      outputPath: '/tmp/out.pdf',
    });
    expect(pdfPath).toBe('/tmp/out.pdf');
    expect(writeFileSpy).toHaveBeenCalledWith('/tmp/out.pdf', Buffer.from('pdf-file'));

    writeFileSpy.mockRestore();
  });

  it('couvre UserService sur les principaux parcours', async () => {
    const repository = {
      findOne: vi.fn(async () => ({ id: 11, userJwt: { id: 101, username: 'john@test.local' } })),
      find: vi.fn(async () => [{ id: 12, userJwt: { username: 'jane@test.local' } }]),
      findOneById: vi.fn(async () => ({ id: 13 })),
      findCurrentUserFromJwtUsername: vi.fn(async () => ({ id: 14 })),
      findCurrentUserFromJwtId: vi.fn(async () => ({ id: 15 })),
      create: vi.fn((dto) => ({ id: 16, ...dto })),
      save: vi.fn(async (dto) => ({ id: dto.id ?? 17, ...dto })),
      findAndCount: vi.fn(async () => [[{ id: 18 }], 1]),
      softDelete: vi.fn(async () => ({ id: 19 })),
      findAll: vi.fn(async () => [{ id: 20 }]),
    };

    const userJwtService = {
      create: vi.fn(async () => ({ id: 201 })),
      findById: vi.fn(async () => ({ id: 201, username: 'created@test.local' })),
      save: vi.fn(async (dto) => dto),
      softRemove: vi.fn(async () => undefined),
    };

    const service = new UserService(repository as never, userJwtService as never);

    await expect(service.findFromUserJwtId(101)).resolves.toEqual(
      expect.objectContaining({ id: 11 }),
    );
    await expect(service.getAll()).resolves.toHaveLength(1);
    await expect(service.findOneById(13)).resolves.toEqual(
      expect.objectContaining({ id: 11 }),
    );
    await expect(service.findWithUsername('jane@test.local')).resolves.toHaveLength(1);
    await expect(service.findCurrentUser('john@test.local')).resolves.toEqual({ id: 14 });
    await expect(service.findCurrentUserById(101)).resolves.toEqual({ id: 15 });

    await expect(
      service.create({
        roles: [UserRoleEnum.Admin],
        userJwt: { username: 'created@test.local', password: 'StrongPassword123!' },
      }),
    ).resolves.toEqual(expect.objectContaining({ id: 16 }));

    await expect(
      service.create({
        roles: [UserRoleEnum.User],
      }),
    ).rejects.toBeInstanceOf(HttpException);

    await expect(
      service.createFromAuthJwt({
        user: { id: 301, username: 'event@test.local' } as never,
      } as never),
    ).resolves.toEqual(expect.objectContaining({ id: 16 }));

    await expect(service.update({ id: 13, firstname: 'Alice' })).resolves.toEqual(
      expect.objectContaining({ id: 13, firstname: 'Alice' }),
    );

    repository.findOneById.mockResolvedValueOnce(undefined as any);
    await expect(service.update({ id: 999, firstname: 'Ghost' })).resolves.toBeUndefined();

    await expect(service.updateAdmin({ id: 13, roles: [UserRoleEnum.User] })).resolves.toEqual(
      expect.objectContaining({ id: 13 }),
    );

    repository.findOneById.mockResolvedValueOnce(undefined as any);
    await expect(service.updateAdmin({ id: 999 })).resolves.toBeUndefined();

    await expect(service.delete(101)).resolves.toEqual({ id: 19 });

    repository.findOne.mockResolvedValueOnce(null as any);
    await expect(service.delete(202)).resolves.toEqual({ id: 19 });

    await expect(
      service.paginate({
        q: 'john',
        role: UserRoleEnum.Admin,
        orderBy: 'username',
        order: 'ASC',
        limit: 10,
        offset: 0,
      } as unknown as PaginateUserDTO),
    ).resolves.toEqual({
      results: [{ id: 18 }],
      count: 1,
    });
  });

  it('couvre AdminUserController sur les parcours nominal et erreur', async () => {
    const service = {
      getAll: vi.fn(async () => [{ id: 1 }]),
      paginate: vi.fn(async () => ({ results: [{ id: 2 }], count: 1 })),
      findOneById: vi.fn(async (id: number) => (id === 404 ? null : { id })),
      create: vi.fn(async (dto) => ({ id: 3, ...dto })),
      updateAdmin: vi.fn(async (dto) => ({ id: dto.id ?? 4, ...dto })),
      delete: vi.fn(async (id: number) => (id === 404 ? null : { id })),
    };

    const userJwtService = {
      findByUsername: vi.fn(async (username: string) =>
        username === 'exists@test.local' ? { id: 99 } : null,
      ),
    };

    const controller = new AdminUserController(service as never, userJwtService as never);

    await expect(controller.getAll()).resolves.toEqual([{ id: 1 }]);
    await expect(
      controller.paginate({ limit: 10, offset: 0 } as PaginateUserDTO),
    ).resolves.toEqual({ results: [{ id: 2 }], count: 1 });
    await expect(controller.getOne(10 as never)).resolves.toEqual({ id: 10 });
    await expect(controller.getOne(404 as never)).rejects.toBeInstanceOf(NotFoundException);

    await expect(
      controller.create({
        firstname: 'John',
        roles: [UserRoleEnum.User],
        userJwt: { username: 'new@test.local', password: 'StrongPassword123!' },
      } as UserCreateForAdminDto),
    ).resolves.toEqual(expect.objectContaining({ id: 3 }));

    await expect(
      controller.create({
        firstname: 'Dup',
        roles: [UserRoleEnum.User],
        userJwt: { username: 'exists@test.local', password: 'StrongPassword123!' },
      } as UserCreateForAdminDto),
    ).rejects.toBeInstanceOf(HttpException);

    service.updateAdmin.mockRejectedValueOnce(new Error('boom'));
    await expect(controller.update({ id: 7, firstname: 'Err' })).rejects.toBeInstanceOf(HttpException);

    await expect(
      controller.updateCurrent({ id: 8, firstname: 'Current' }),
    ).resolves.toEqual(expect.objectContaining({ id: 8 }));

    await expect(controller.remove(3 as never)).resolves.toEqual({ id: 3 });
    await expect(controller.remove(404 as never)).rejects.toBeInstanceOf(NotFoundException);
  });
});
