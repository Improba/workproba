import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { UserController } from '@users/controllers/user.controller';
import { UserService } from '@users/services/user.service';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';
import { JwtAuthGuard } from '@users/guards/jwt-auth.guard';
import { UserRolesGuard } from '@users/guards/user-roles.guard';
import { User, UserRoleEnum } from '@users/entities/user.entity';
import {
  createHttpTestApp,
  createMockAuthGuard,
} from '@lib-improba/testing/http-test-app';

const fakeJwtUser = { id: 1, roles: [UserRoleEnum.User] };
const authGuard = createMockAuthGuard(fakeJwtUser);

describe('UserController (HTTP)', () => {
  let app: INestApplication;

  const mockUser = { id: 1, firstname: 'John', lastname: 'Doe' } as User;

  const mockUserService = {
    findOneById: vi.fn(),
    update: vi.fn(),
  };

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [UserController],
      providers: [
        { provide: UserService, useValue: mockUserService },
        { provide: UserJwtService, useValue: {} },
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

  describe('GET /users/current', () => {
    it('returns 200 and current user', async () => {
      mockUserService.findOneById.mockResolvedValue(mockUser);

      const res = await request(app.getHttpServer())
        .get('/users/current')
        .expect(200);

      expect(res.body).toMatchObject({ id: 1, firstname: 'John' });
      expect(mockUserService.findOneById).toHaveBeenCalledWith(1);
    });

    it('returns 404 when user does not exist', async () => {
      mockUserService.findOneById.mockResolvedValue(null);

      await request(app.getHttpServer()).get('/users/current').expect(404);
    });
  });

  describe('PATCH /users/current', () => {
    it('returns 200 and updated user', async () => {
      const updated = { ...mockUser, firstname: 'Jane' };
      mockUserService.update.mockResolvedValue(updated);

      const res = await request(app.getHttpServer())
        .patch('/users/current')
        .send({ firstname: 'Jane' })
        .expect(200);

      expect(res.body.firstname).toBe('Jane');
      expect(mockUserService.update).toHaveBeenCalledWith({
        firstname: 'Jane',
        id: 1,
      });
    });

    it('returns 400 when payload contains unknown fields', async () => {
      await request(app.getHttpServer())
        .patch('/users/current')
        .send({ firstname: 'Jane', unknownField: true })
        .expect(400);
    });

    it('returns 500 when update fails', async () => {
      mockUserService.update.mockResolvedValue(null);

      await request(app.getHttpServer())
        .patch('/users/current')
        .send({ firstname: 'Jane' })
        .expect(500);
    });
  });
});
