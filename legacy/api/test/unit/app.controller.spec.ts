import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { AppController } from 'src/app.controller';
import { AppService } from 'src/app.service';
import { createHttpTestApp } from '@lib-improba/testing/http-test-app';

describe('AppController (HTTP)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [AppService],
    }).compile();

    app = await createHttpTestApp(moduleFixture);
  });

  afterAll(async () => {
    await app.close();
  });

  describe('GET /', () => {
    it('returns 200 and HTML page with app name and version', async () => {
      const originalName = process.env.npm_package_name;
      const originalVersion = process.env.npm_package_version;
      process.env.npm_package_name = 'workproba-api';
      process.env.npm_package_version = '0.0.1';

      const res = await request(app.getHttpServer()).get('/').expect(200);

      expect(res.text).toContain('workproba-api');
      expect(res.text).toContain('0.0.1');
      expect(res.text).toContain('<html>');

      process.env.npm_package_name = originalName;
      process.env.npm_package_version = originalVersion;
    });
  });
});
