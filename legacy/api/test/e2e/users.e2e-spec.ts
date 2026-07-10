import { INestApplication } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { EventEmitterModule } from '@nestjs/event-emitter';
import { MikroORM } from '@mikro-orm/core';
import { MikroOrmModule } from '@mikro-orm/nestjs';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';

import { UserRoleEnum } from '@core/users/entities/user.entity';
import { UsersModule } from '@core/users/index.module';
import { UserService } from '@core/users/services/user.service';
import { createHttpTestApp } from '@lib-improba/testing/http-test-app';
import { testDatabaseConfig } from '@test/config/database.config';
import {
  closeTestDatabase,
  generateUniqueId,
  initTestDatabase,
} from '@test/test.utils';

type SeededUser = {
  id: number;
  username: string;
  password: string;
};

describe('Users (e2e)', () => {
  let app: INestApplication;
  let orm: MikroORM;
  let userService: UserService;

  beforeAll(async () => {
    process.env.JWT_SECRET = process.env.JWT_SECRET || 'test-secret-key';

    orm = await initTestDatabase();

    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({ isGlobal: true }),
        MikroOrmModule.forRoot(testDatabaseConfig),
        EventEmitterModule.forRoot(),
        UsersModule,
      ],
    }).compile();

    app = await createHttpTestApp(moduleFixture);
    userService = moduleFixture.get(UserService);
  });

  afterAll(async () => {
    if (app) await app.close();
    if (orm) await closeTestDatabase(orm);
  });

  async function seedUser(roles: UserRoleEnum[]): Promise<SeededUser> {
    const username = `${generateUniqueId('users-e2e')}@example.com`;
    const password = 'StrongPassword123!';
    const created = await userService.create({
      roles,
      userJwt: {
        username,
        password,
        activated: true,
      },
    });

    return {
      id: created.id,
      username,
      password,
    };
  }

  async function login(username: string, password: string): Promise<string> {
    const response = await request(app.getHttpServer())
      .post('/auth-jwt/login')
      .send({ username, password })
      .expect(200);

    return response.body.token as string;
  }

  it('GET /users/current returns 401 without token', async () => {
    await request(app.getHttpServer()).get('/users/current').expect(401);
  });

  it('GET /users/current returns connected user', async () => {
    const user = await seedUser([UserRoleEnum.User]);
    const token = await login(user.username, user.password);

    const response = await request(app.getHttpServer())
      .get('/users/current')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);

    expect(response.body.id).toBe(user.id);
    expect(response.body.roles).toContain(UserRoleEnum.User);
    expect(response.body.userJwt.username).toBe(user.username);
  });

  it('PATCH /users/current updates connected user', async () => {
    const user = await seedUser([UserRoleEnum.User]);
    const token = await login(user.username, user.password);

    const response = await request(app.getHttpServer())
      .patch('/users/current')
      .set('Authorization', `Bearer ${token}`)
      .send({ firstname: 'Alice', preferDarkTheme: false })
      .expect(200);

    expect(response.body.firstname).toBe('Alice');
    expect(response.body.preferDarkTheme).toBe(false);
  });

  it('GET /users-admin returns 403 for non-admin user', async () => {
    const user = await seedUser([UserRoleEnum.User]);
    const token = await login(user.username, user.password);

    await request(app.getHttpServer())
      .get('/users-admin')
      .set('Authorization', `Bearer ${token}`)
      .expect(403);
  });

  it('GET /users-admin returns users for admin', async () => {
    const admin = await seedUser([UserRoleEnum.Admin]);
    const token = await login(admin.username, admin.password);

    const response = await request(app.getHttpServer())
      .get('/users-admin')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);

    expect(Array.isArray(response.body)).toBe(true);
    expect(response.body.length).toBeGreaterThan(0);
  });

  it('POST /users-admin creates a new user with admin token', async () => {
    const admin = await seedUser([UserRoleEnum.Admin]);
    const token = await login(admin.username, admin.password);

    const newUsername = `${generateUniqueId('users-admin-create')}@example.com`;

    const response = await request(app.getHttpServer())
      .post('/users-admin')
      .set('Authorization', `Bearer ${token}`)
      .send({
        firstname: 'New',
        lastname: 'User',
        roles: [UserRoleEnum.User],
        userJwt: {
          username: newUsername,
          password: 'NewStrongPassword123!',
        },
      })
      .expect(201);

    expect(response.body.id).toBeDefined();
    expect(response.body.roles).toContain(UserRoleEnum.User);
  });
});
