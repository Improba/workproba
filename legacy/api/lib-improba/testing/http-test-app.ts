import {
  INestApplication,
  ValidationPipe,
  ExecutionContext,
} from '@nestjs/common';
import { Test, TestingModule } from '@nestjs/testing';

/** ValidationPipe aligné sur `main.ts` pour des tests HTTP réalistes. */
export async function createHttpTestApp(
  moduleFixture: TestingModule,
): Promise<INestApplication> {
  const app = moduleFixture.createNestApplication();
  app.useGlobalPipes(
    new ValidationPipe({
      transform: true,
      whitelist: true,
      forbidNonWhitelisted: true,
      forbidUnknownValues: true,
    }),
  );
  await app.init();
  return app;
}

/** Mock de guard JWT / rôles : injecte `req.user` et autorise la requête. */
export function createMockAuthGuard<TUser extends { id: number }>(
  user: TUser,
): { canActivate: (context: ExecutionContext) => boolean } {
  return {
    canActivate(context: ExecutionContext): boolean {
      const req = context.switchToHttp().getRequest();
      req.user = user;
      return true;
    },
  };
}

export type { TestingModule };
