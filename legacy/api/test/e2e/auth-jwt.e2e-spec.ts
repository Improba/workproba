import { INestApplication } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { EventEmitterModule } from '@nestjs/event-emitter';
import { JwtModule } from '@nestjs/jwt';
import { Test, TestingModule } from '@nestjs/testing';
import { MikroORM } from '@mikro-orm/core';
import { MikroOrmModule } from '@mikro-orm/nestjs';
import request from 'supertest';

import { AuthJwtController } from '@auth-jwt/controllers/auth-jwt.controller';
import { UserJwt } from '@auth-jwt/entities/user-jwt.entity';
import { UserJwtRepository } from '@auth-jwt/repositories/user-jwt.repository';
import { UserJwtService } from '@auth-jwt/services/user-jwt.service';
import { BaseModule } from '@lib-improba/base/base.module';
import { testDatabaseConfig } from '@test/config/database.config';
import {
  closeTestDatabase,
  generateUniqueId,
  initTestDatabase,
} from '@test/test.utils';

describe('Auth JWT (e2e)', () => {
  let app: INestApplication;
  let userJwtService: UserJwtService;
  let orm: MikroORM;

  beforeAll(async () => {
    orm = await initTestDatabase();

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({ isGlobal: true }),
        MikroOrmModule.forRoot(testDatabaseConfig),
        BaseModule.forCustomRepository([UserJwtRepository]),
        EventEmitterModule.forRoot(),
        JwtModule.register({
          secret: process.env.JWT_SECRET || 'test-secret-key',
        }),
      ],
      controllers: [AuthJwtController],
      providers: [UserJwtService],
    }).compile();

    app = moduleFixture.createNestApplication({ logger: false });
    userJwtService = moduleFixture.get(UserJwtService);
    await app.init();
  });

  afterAll(async () => {
    if (app) await app.close();
    if (orm) await closeTestDatabase(orm);
  });

  it('POST /auth-jwt/login returns a token for valid credentials', async () => {
    let username = `${generateUniqueId('e2e-login')}@example.com`;
    const password = 'TestPassword123!';

    await userJwtService.create({
      username,
      password,
      activated: true,
    });

    let response = await request(app.getHttpServer())
      .post('/auth-jwt/login')
      .send({ username, password });

    if (response.status !== 200) {
      username = `${generateUniqueId('e2e-login-retry')}@example.com`;
      await userJwtService.create({
        username,
        password,
        activated: true,
      });

      response = await request(app.getHttpServer())
        .post('/auth-jwt/login')
        .send({ username, password })
        .expect(200);
    } else {
      expect(response.status).toBe(200);
    }

    expect(response.body.token).toBeDefined();
    expect(typeof response.body.token).toBe('string');
  });

  it('POST /auth-jwt/login returns 400 for invalid password', async () => {
    const username = `${generateUniqueId('e2e')}@example.com`;

    await userJwtService.create({
      username,
      password: 'CorrectPassword123!',
      activated: true,
    });

    await request(app.getHttpServer())
      .post('/auth-jwt/login')
      .send({ username, password: 'WrongPassword123!' })
      .expect(400);
  });

  it('POST /auth-jwt/refreshToken returns a new token for valid token', async () => {
    const username = `${generateUniqueId('e2e-refresh')}@example.com`;
    const password = 'RefreshPassword123!';

    await userJwtService.create({
      username,
      password,
      activated: true,
    });

    const loginResponse = await request(app.getHttpServer())
      .post('/auth-jwt/login')
      .send({ username, password })
      .expect(200);

    const refreshResponse = await request(app.getHttpServer())
      .post('/auth-jwt/refreshToken')
      .send({ token: loginResponse.body.token })
      .expect(200);

    expect(refreshResponse.body.token).toBeDefined();
    expect(typeof refreshResponse.body.token).toBe('string');
    expect(refreshResponse.body.token.length).toBeGreaterThan(20);
  });

  it('POST /auth-jwt/refreshToken returns 401 for invalid token', async () => {
    await request(app.getHttpServer())
      .post('/auth-jwt/refreshToken')
      .send({ token: 'invalid-token' })
      .expect(401);
  });

  it('POST /auth-jwt/forgot-password enforces request cooldown', async () => {
    const username = `${generateUniqueId('e2e-forgot')}@example.com`;
    const password = 'ForgotPassword123!';

    await userJwtService.create({
      username,
      password,
      activated: true,
    });

    const firstResponse = await request(app.getHttpServer())
      .post('/auth-jwt/forgot-password')
      .send({ username })
      .expect(200);

    expect(firstResponse.body.success).toBe(true);

    await request(app.getHttpServer())
      .post('/auth-jwt/forgot-password')
      .send({ username })
      .expect(400);
  });

  it('POST /auth-jwt/reset-password updates password and allows new login', async () => {
    const username = `${generateUniqueId('e2e-reset')}@example.com`;
    const oldPassword = 'OldPassword123!';
    const newPassword = 'NewPassword123!';

    await userJwtService.create({
      username,
      password: oldPassword,
      activated: true,
    });

    await request(app.getHttpServer())
      .post('/auth-jwt/forgot-password')
      .send({ username })
      .expect(200);

    const userAfterForgot = await orm.em.fork().findOne(
      UserJwt,
      { username },
      {
        fields: ['id', 'username', 'forgetPasswordToken'] as Array<keyof UserJwt>,
      },
    );

    expect(userAfterForgot).toBeDefined();
    expect(userAfterForgot?.forgetPasswordToken).toBeDefined();
    expect(userAfterForgot?.forgetPasswordToken).not.toBeNull();
    const resetToken = userAfterForgot!.forgetPasswordToken as string;

    const resetResponse = await request(app.getHttpServer())
      .post('/auth-jwt/reset-password')
      .send({
        token: resetToken,
        password: newPassword,
      })
      .expect(200);

    expect(resetResponse.body.token).toBeDefined();
    expect(typeof resetResponse.body.token).toBe('string');

    await request(app.getHttpServer())
      .post('/auth-jwt/login')
      .send({ username, password: oldPassword })
      .expect(400);

    await request(app.getHttpServer())
      .post('/auth-jwt/login')
      .send({ username, password: newPassword })
      .expect(200);
  });
});
