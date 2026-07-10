import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { AdminUserController } from '@users/controllers/admin/admin-user.controller';
import { UserService } from '@users/services/user.service';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';
import { JwtAuthGuard } from '@users/guards/jwt-auth.guard';
import { UserRolesGuard } from '@users/guards/user-roles.guard';
import { User, UserRoleEnum } from '@users/entities/user.entity';
import {
  createHttpTestApp,
  createMockAuthGuard,
} from '@lib-improba/testing/http-test-app';

const fakeAdminUser = { id: 1, roles: [UserRoleEnum.Admin] };
const authGuard = createMockAuthGuard(fakeAdminUser);

describe('AdminUserController (HTTP)', () => {
  let app: INestApplication;

  const mockUser = {
    id: 1,
    firstname: 'Admin',
    roles: [UserRoleEnum.Admin],
  } as User;

  const mockUserService = {
    getAll: vi.fn(),
    paginate: vi.fn(),
    findOneById: vi.fn(),
    create: vi.fn(),
    updateAdmin: vi.fn(),
    delete: vi.fn(),
  };

  const mockUserJwtService = {
    findByUsername: vi.fn(),
  };

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [AdminUserController],
      providers: [
        { provide: UserService, useValue: mockUserService },
        { provide: UserJwtService, useValue: mockUserJwtService },
      ],
    })
      .overrideGuard(JwtAuthGuard)
      .useValue(authGuard)
      .overrideGuard(UserRolesGuard)
      .useValue(authGuard)
      .compile();

    app = await createHttpTestApp(moduleFixture);
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('GET /users-admin', () => {
    it('returns 200 and all users', async () => {
      mockUserService.getAll.mockResolvedValue([mockUser]);

      const res = await request(app.getHttpServer())
        .get('/users-admin')
        .expect(200);

      expect(res.body).toEqual([mockUser]);
    });
  });

  describe('GET /users-admin/paginate', () => {
    it('returns 200 and paginated results', async () => {
      const paginated = { results: [mockUser], count: 1 };
      mockUserService.paginate.mockResolvedValue(paginated);

      const res = await request(app.getHttpServer())
        .get('/users-admin/paginate')
        .query({ limit: 10, offset: 0 })
        .expect(200);

      expect(res.body).toEqual(paginated);
    });
  });

  describe('GET /users-admin/:id', () => {
    it('returns 200 and user by id', async () => {
      mockUserService.findOneById.mockResolvedValue(mockUser);

      const res = await request(app.getHttpServer())
        .get('/users-admin/1')
        .expect(200);

      expect(res.body).toMatchObject({ id: 1, firstname: 'Admin' });
    });

    it('returns 404 when user not found', async () => {
      mockUserService.findOneById.mockResolvedValue(null);

      await request(app.getHttpServer()).get('/users-admin/99').expect(404);
    });
  });

  describe('POST /users-admin', () => {
    it('returns 201 when user is created', async () => {
      mockUserJwtService.findByUsername.mockResolvedValue(null);
      mockUserService.create.mockResolvedValue(mockUser);

      const res = await request(app.getHttpServer())
        .post('/users-admin')
        .send({
          roles: [UserRoleEnum.User],
          userJwt: { username: 'new@example.com', password: 'Password123!' },
        })
        .expect(201);

      expect(res.body).toMatchObject({ id: 1 });
    });

    it('returns 400 when username already exists', async () => {
      mockUserJwtService.findByUsername.mockResolvedValue({ id: 2 });

      await request(app.getHttpServer())
        .post('/users-admin')
        .send({
          roles: [UserRoleEnum.User],
          userJwt: { username: 'taken@example.com', password: 'pass' },
        })
        .expect(400);
    });

    it('returns 400 when roles are missing from payload', async () => {
      await request(app.getHttpServer())
        .post('/users-admin')
        .send({
          userJwt: { username: 'new@example.com', password: 'pass' },
        })
        .expect(400);
    });
  });

  describe('PATCH /users-admin', () => {
    it('returns 200 when user is updated', async () => {
      mockUserService.updateAdmin.mockResolvedValue(mockUser);

      const res = await request(app.getHttpServer())
        .patch('/users-admin')
        .send({ id: 1, firstname: 'Updated' })
        .expect(200);

      expect(res.body).toMatchObject({ firstname: 'Admin' });
    });

    it('returns 400 when update fails', async () => {
      mockUserService.updateAdmin.mockRejectedValue(new Error('fail'));

      await request(app.getHttpServer())
        .patch('/users-admin')
        .send({ id: 1, firstname: 'x' })
        .expect(400);
    });
  });

  describe('DELETE /users-admin/:id', () => {
    it('returns 200 when user is removed', async () => {
      mockUserService.delete.mockResolvedValue(mockUser);

      const res = await request(app.getHttpServer())
        .delete('/users-admin/1')
        .expect(200);

      expect(res.body).toMatchObject({ id: 1 });
    });

    it('returns 404 when user not found', async () => {
      mockUserService.delete.mockResolvedValue(null);

      await request(app.getHttpServer()).delete('/users-admin/99').expect(404);
    });
  });
});
