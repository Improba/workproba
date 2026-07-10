import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ExecutionContext } from '@nestjs/common';
import request from 'supertest';
import { QuoteController } from '@core/quotes/quote.controller';
import { QuoteService } from '@core/quotes/quote.service';
import { JwtAuthGuard } from '@users/guards/jwt-auth.guard';
import { UserRolesGuard } from '@users/guards/user-roles.guard';
import { UserRoleEnum } from '@users/entities/user.entity';
import { createHttpTestApp } from '@lib-improba/testing/http-test-app';

const fakeJwtUser = { id: 1, roles: [UserRoleEnum.User] };

const authGuardMock = {
  canActivate(context: ExecutionContext): boolean {
    context.switchToHttp().getRequest().user = fakeJwtUser;
    return true;
  },
};

describe('QuoteController (HTTP)', () => {
  let app: INestApplication;

  const mockQuoteService = {
    generateRandomQuote: vi.fn(),
  };

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      controllers: [QuoteController],
      providers: [{ provide: QuoteService, useValue: mockQuoteService }],
    })
      .overrideGuard(JwtAuthGuard)
      .useValue(authGuardMock)
      .overrideGuard(UserRolesGuard)
      .useValue(authGuardMock)
      .compile();

    app = await createHttpTestApp(moduleFixture);
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('GET /quotes/random', () => {
    it('returns 200 and a quote', async () => {
      const quote = { quote: 'Les étoiles dansent dans un ciel infini.' };
      mockQuoteService.generateRandomQuote.mockReturnValue(quote);

      const res = await request(app.getHttpServer())
        .get('/quotes/random')
        .expect(200);

      expect(res.body).toEqual(quote);
      expect(mockQuoteService.generateRandomQuote).toHaveBeenCalled();
    });
  });
});
