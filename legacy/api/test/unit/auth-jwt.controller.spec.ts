import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import request from 'supertest';

import { AuthJwtController } from '@auth-jwt/controllers/auth-jwt.controller';
import { UserJwtService } from '@auth-jwt/services/user-jwt.service';
import { UserJwtRepository } from '@auth-jwt/repositories/user-jwt.repository';
import { UserJwt } from '@auth-jwt/entities/user-jwt.entity';
import { createHttpTestApp } from '@lib-improba/testing/http-test-app';

describe('AuthJwtController (HTTP)', () => {
  let app: INestApplication;

  const mockUser: UserJwt = {
    id: 1,
    username: 'test@example.com',
  } as UserJwt;

  const mockUserJwtService = {
    findByUsernamePassword: vi.fn(),
    login: vi.fn(),
    createNewTokenFromPreviousOne: vi.fn(),
    sendMailForNewPassword: vi.fn(),
    changePasswordUser: vi.fn(),
  };

  const mockConfigService = {
    get: vi.fn((key: string, defaultValue?: string) => {
      if (key === 'FRONTEND_URL') return 'http://localhost:9000';
      return defaultValue;
    }),
  };

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [AuthJwtController],
      providers: [
        { provide: UserJwtService, useValue: mockUserJwtService },
        { provide: UserJwtRepository, useValue: {} },
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();

    app = await createHttpTestApp(moduleFixture);
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('POST /auth-jwt/login', () => {
    it('returns 200 and token when credentials are valid', async () => {
      mockUserJwtService.findByUsernamePassword.mockResolvedValue(mockUser);
      mockUserJwtService.login.mockReturnValue('jwt-token');

      const res = await request(app.getHttpServer())
        .post('/auth-jwt/login')
        .send({ username: 'test@example.com', password: 'Password123!' })
        .expect(200);

      expect(res.body).toEqual({ token: 'jwt-token' });
      expect(mockUserJwtService.findByUsernamePassword).toHaveBeenCalledWith(
        'test@example.com',
        'Password123!',
      );
    });

    it('returns 400 when credentials are invalid', async () => {
      const { BadRequestException } = await import('@nestjs/common');
      mockUserJwtService.findByUsernamePassword.mockRejectedValue(
        new BadRequestException('Identifiants incorrects'),
      );

      await request(app.getHttpServer())
        .post('/auth-jwt/login')
        .send({ username: 'test@example.com', password: 'wrong' })
        .expect(400);
    });

    it('accepts JSON payload with username and password fields', async () => {
      mockUserJwtService.findByUsernamePassword.mockResolvedValue(mockUser);
      mockUserJwtService.login.mockReturnValue('jwt-token');

      await request(app.getHttpServer())
        .post('/auth-jwt/login')
        .set('Content-Type', 'application/json')
        .send(JSON.stringify({ username: 'a@b.com', password: 'secret' }))
        .expect(200);
    });
  });

  describe('POST /auth-jwt/refreshToken', () => {
    it('returns 200 and new token when refresh succeeds', async () => {
      mockUserJwtService.createNewTokenFromPreviousOne.mockReturnValue(
        'new-jwt-token',
      );

      const res = await request(app.getHttpServer())
        .post('/auth-jwt/refreshToken')
        .send({ token: 'old-token' })
        .expect(200);

      expect(res.body).toEqual({ token: 'new-jwt-token' });
    });

    it('returns 401 when token is invalid', async () => {
      mockUserJwtService.createNewTokenFromPreviousOne.mockReturnValue(null);

      await request(app.getHttpServer())
        .post('/auth-jwt/refreshToken')
        .send({ token: 'invalid-token' })
        .expect(401);
    });

    it('returns 401 when token field is missing', async () => {
      mockUserJwtService.createNewTokenFromPreviousOne.mockReturnValue(null);

      await request(app.getHttpServer())
        .post('/auth-jwt/refreshToken')
        .send({})
        .expect(401);
    });
  });

  describe('GET /auth-jwt/logout', () => {
    it('redirects to frontend URL', async () => {
      const res = await request(app.getHttpServer())
        .get('/auth-jwt/logout')
        .expect(302);

      expect(res.headers.location).toBe('http://localhost:9000');
    });
  });

  describe('POST /auth-jwt/forgot-password', () => {
    it('returns 200 when user exists', async () => {
      mockUserJwtService.sendMailForNewPassword.mockResolvedValue(mockUser);

      const res = await request(app.getHttpServer())
        .post('/auth-jwt/forgot-password')
        .send({ username: 'test@example.com' })
        .expect(200);

      expect(res.body.success).toBe(true);
      expect(res.body.message).toBe(
        'Mail de récupération de mot de passe envoyé',
      );
    });

    it('returns 400 when user does not exist', async () => {
      mockUserJwtService.sendMailForNewPassword.mockResolvedValue(null);

      await request(app.getHttpServer())
        .post('/auth-jwt/forgot-password')
        .send({ username: 'missing@example.com' })
        .expect(400);
    });
  });

  describe('POST /auth-jwt/reset-password', () => {
    it('returns 200 and token when password reset succeeds', async () => {
      mockUserJwtService.changePasswordUser.mockResolvedValue({ user: mockUser });
      mockUserJwtService.login.mockReturnValue('reset-jwt-token');

      const res = await request(app.getHttpServer())
        .post('/auth-jwt/reset-password')
        .send({ token: 'reset-token', password: 'NewPassword123!' })
        .expect(200);

      expect(res.body.token).toBe('reset-jwt-token');
      expect(mockUserJwtService.changePasswordUser).toHaveBeenCalledWith(
        'reset-token',
        'NewPassword123!',
      );
    });

    it('returns 400 when token is invalid', async () => {
      mockUserJwtService.changePasswordUser.mockResolvedValue({ user: null });

      await request(app.getHttpServer())
        .post('/auth-jwt/reset-password')
        .send({ token: 'invalid-token', password: 'NewPassword123!' })
        .expect(400);
    });

    it('returns 400 when password is missing from payload', async () => {
      await request(app.getHttpServer())
        .post('/auth-jwt/reset-password')
        .send({ token: 'some-token' })
        .expect(400);
    });
  });
});
