import { INestApplication } from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';
import request from 'supertest';

import { AppController } from 'src/app.controller';
import { AppService } from 'src/app.service';

describe('App (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [AppService],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app?.close();
  });

  it('GET / returns API welcome HTML', async () => {
    const res = await request(app.getHttpServer()).get('/').expect(200);

    expect(res.text).toContain('workproba-api');
  });
});
