import { Test, TestingModule } from '@nestjs/testing';
import {
  BadRequestException,
  NotFoundException,
} from '@nestjs/common';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';

import { UserJwtService } from '@auth-jwt/services/user-jwt.service';
import { UserJwtRepository } from '@auth-jwt/repositories/user-jwt.repository';
import { UserJwt } from '@auth-jwt/entities/user-jwt.entity';

vi.mock('bcrypt', () => ({
  hash: vi.fn().mockResolvedValue('hashed-password'),
  compare: vi.fn(),
}));

vi.mock('@sendgrid/mail', () => ({
  setApiKey: vi.fn(),
  send: vi.fn().mockResolvedValue(undefined),
}));

import * as bcrypt from 'bcrypt';
import * as sgMail from '@sendgrid/mail';

describe('UserJwtService', () => {
  let service: UserJwtService;

  const mockUser: UserJwt = {
    id: 1,
    username: 'test@example.com',
    password: 'hashed-password',
    activated: true,
  } as UserJwt;

  const mockQueryBuilder = {
    andWhere: vi.fn().mockReturnThis(),
    getSingleResult: vi.fn(),
  };

  const mockRepository = {
    create: vi.fn((data: Partial<UserJwt>) => ({ id: 1, ...data })),
    save: vi.fn(async (user: UserJwt) => user),
    findOne: vi.fn(),
    findOneById: vi.fn(),
    update: vi.fn(),
    softRemove: vi.fn(),
    createQueryBuilder: vi.fn(() => mockQueryBuilder),
  };

  const mockEventEmitter = {
    emitAsync: vi.fn().mockResolvedValue(undefined),
  };

  const mockJwtService = {
    sign: vi.fn().mockReturnValue('jwt-token'),
    verify: vi.fn().mockReturnValue(true),
    decode: vi.fn(),
    verifyAsync: vi.fn(),
  };

  const mockConfigService = {
    get: vi.fn((key: string, defaultValue?: string) => {
      const values: Record<string, string> = {
        JWT_EXPIRES_IN: '1h',
        FRONTEND_URL: 'http://localhost:9000',
      };
      return values[key] ?? defaultValue;
    }),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        UserJwtService,
        { provide: UserJwtRepository, useValue: mockRepository },
        { provide: EventEmitter2, useValue: mockEventEmitter },
        { provide: JwtService, useValue: mockJwtService },
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();

    service = module.get<UserJwtService>(UserJwtService);
    vi.clearAllMocks();
    vi.mocked(bcrypt.compare).mockResolvedValue(true as never);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('create', () => {
    it('should create a new user with encrypted password', async () => {
      const result = await service.create({
        username: 'test@example.com',
        password: 'Password123!',
      });

      expect(result.id).toBe(1);
      expect(result.username).toBe('test@example.com');
      expect(bcrypt.hash).toHaveBeenCalledWith('Password123!', 10);
      expect(mockRepository.save).toHaveBeenCalled();
    });
  });

  describe('findByUsernamePassword', () => {
    it('should return user when credentials are valid', async () => {
      mockRepository.findOne
        .mockResolvedValueOnce({ ...mockUser, password: 'hashed' })
        .mockResolvedValueOnce(mockUser);

      const result = await service.findByUsernamePassword(
        'test@example.com',
        'Password123!',
      );

      expect(result).toEqual(mockUser);
    });

    it('should throw BadRequestException when credentials are invalid', async () => {
      mockRepository.findOne.mockResolvedValue({
        ...mockUser,
        password: 'hashed',
      });
      vi.mocked(bcrypt.compare).mockResolvedValue(false as never);

      await expect(
        service.findByUsernamePassword('test@example.com', 'wrong'),
      ).rejects.toThrow(BadRequestException);
    });

    it('should throw when user exists but full user not found', async () => {
      mockRepository.findOne
        .mockResolvedValueOnce({ ...mockUser, password: 'hashed', id: 1 })
        .mockResolvedValueOnce(null);

      await expect(
        service.findByUsernamePassword('test@example.com', 'Password123!'),
      ).rejects.toThrow();
    });
  });

  describe('login', () => {
    it('should generate a valid JWT token', () => {
      const token = service.login(mockUser);

      expect(token).toBe('jwt-token');
      expect(mockJwtService.sign).toHaveBeenCalledWith(
        { id: mockUser.id, username: mockUser.username },
        expect.objectContaining({ expiresIn: '1h' }),
      );
    });
  });

  describe('createNewTokenFromPreviousOne', () => {
    it('should create new token from valid token', () => {
      mockJwtService.decode.mockReturnValue({
        id: 1,
        username: 'test@example.com',
      });

      const result = service.createNewTokenFromPreviousOne('valid-token');

      expect(result).toBe('jwt-token');
    });

    it('should return null for invalid token', () => {
      mockJwtService.verify.mockReturnValue(false);

      const result = service.createNewTokenFromPreviousOne('invalid-token');

      expect(result).toBeNull();
    });

    it('should return null when payload is invalid', () => {
      mockJwtService.decode.mockReturnValue(null);

      const result = service.createNewTokenFromPreviousOne('token');

      expect(result).toBeNull();
    });

    it('should return null when payload lacks id or username', () => {
      mockJwtService.decode.mockReturnValue({ id: 1 });

      expect(service.createNewTokenFromPreviousOne('token')).toBeNull();
    });

    it('should return null when verify throws', () => {
      mockJwtService.verify.mockImplementation(() => {
        throw new Error('invalid');
      });

      expect(service.createNewTokenFromPreviousOne('bad')).toBeNull();
    });
  });

  describe('activate', () => {
    it('should activate user with valid token', async () => {
      const user = { ...mockUser, activated: false, activationToken: 'tok' };
      mockRepository.findOne.mockResolvedValue(user);
      mockRepository.save.mockResolvedValue({ ...user, activated: true });

      const result = await service.activate('tok');

      expect(result.success).toBe(true);
      expect(mockEventEmitter.emitAsync).toHaveBeenCalled();
    });

    it('should return success when already activated', async () => {
      mockRepository.findOne.mockResolvedValue({
        ...mockUser,
        activated: true,
        activationToken: 'tok',
      });

      const result = await service.activate('tok');

      expect(result.success).toBe(true);
      expect(result.message).toBe('Compte déjà activé');
    });

    it('should return failure when token is invalid', async () => {
      mockRepository.findOne.mockResolvedValue(null);

      const result = await service.activate('invalid');

      expect(result.success).toBe(false);
    });
  });

  describe('findByUsername', () => {
    it('should find user by username', async () => {
      mockQueryBuilder.getSingleResult.mockResolvedValue(mockUser);

      const user = await service.findByUsername('test@example.com');

      expect(user).toEqual(mockUser);
    });
  });

  describe('sendMailForNewPassword', () => {
    it('should generate reset password token', async () => {
      mockRepository.findOne.mockResolvedValue({ ...mockUser });

      const result = await service.sendMailForNewPassword('test@example.com');

      expect(result.forgetPasswordToken).toBeDefined();
      expect(mockRepository.save).toHaveBeenCalled();
    });

    it('should throw BadRequestException when user does not exist', async () => {
      mockRepository.findOne.mockResolvedValue(null);

      await expect(
        service.sendMailForNewPassword('missing@example.com'),
      ).rejects.toThrow(BadRequestException);
    });

    it('should throw when reset requested within 10 minutes', async () => {
      mockRepository.findOne.mockResolvedValue({
        ...mockUser,
        lastResetPasswordAt: new Date(),
      });

      await expect(
        service.sendMailForNewPassword('test@example.com'),
      ).rejects.toThrow(BadRequestException);
    });

    it('should send email when SendGrid is configured', async () => {
      mockConfigService.get.mockImplementation((key: string) => {
        if (key === 'SENDGRID_API_KEY') return 'sg-key';
        if (key === 'EMAIL_FROM') return 'from@test.com';
        if (key === 'APP_NAME') return 'App';
        if (key === 'FRONTEND_URL') return 'http://localhost';
        return '1h';
      });
      mockRepository.findOne.mockResolvedValue({ ...mockUser });

      await service.sendMailForNewPassword('test@example.com');

      expect(sgMail.send).toHaveBeenCalled();
    });
  });

  describe('changePasswordUser', () => {
    it('should change password via recovery token', async () => {
      mockRepository.findOne.mockResolvedValue({ ...mockUser, id: 1 });
      mockRepository.update.mockResolvedValue(undefined);

      const result = await service.changePasswordUser('token', 'NewPass1!');

      expect(result.user).toBeDefined();
      expect(mockRepository.update).toHaveBeenCalled();
    });
  });

  describe('findByRecuperationToken', () => {
    it('should throw when token is invalid', async () => {
      mockRepository.findOne.mockResolvedValue(null);

      await expect(service.findByRecuperationToken('bad')).rejects.toThrow(
        BadRequestException,
      );
    });
  });

  describe('findUserFromAuthToken', () => {
    it('should return user from valid token', async () => {
      mockJwtService.verifyAsync.mockResolvedValue({ id: 1, username: 'a@b.com' });
      mockRepository.findOne.mockResolvedValue(mockUser);

      const user = await service.findUserFromAuthToken('jwt');

      expect(user).toEqual(mockUser);
    });

    it('should throw when token payload is invalid', async () => {
      mockJwtService.verifyAsync.mockResolvedValue(null);

      await expect(service.findUserFromAuthToken('jwt')).rejects.toThrow(
        BadRequestException,
      );
    });
  });

  describe('save and softRemove', () => {
    it('should save user', async () => {
      mockRepository.save.mockResolvedValue(mockUser);

      const result = await service.save(mockUser);

      expect(result).toEqual(mockUser);
    });

    it('should soft remove user', async () => {
      mockRepository.softRemove.mockResolvedValue(mockUser);

      const result = await service.softRemove(mockUser);

      expect(result).toEqual(mockUser);
    });
  });

  describe('changePassword', () => {
    it('should change user password', async () => {
      mockRepository.findOne.mockResolvedValue({ ...mockUser });

      const result = await service.changePassword(1, 'NewPassword456!');

      expect(result.user).toBeDefined();
      expect(bcrypt.hash).toHaveBeenCalledWith('NewPassword456!', 10);
    });

    it('should throw NotFoundException when user does not exist', async () => {
      mockRepository.findOne.mockResolvedValue(null);

      await expect(service.changePassword(99999, 'pass')).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('findById', () => {
    it('should find user by id', async () => {
      mockRepository.findOneById.mockResolvedValue(mockUser);

      const user = await service.findById(1);

      expect(user).toEqual(mockUser);
    });

    it('should throw NotFoundException when user does not exist', async () => {
      mockRepository.findOneById.mockResolvedValue(null);

      await expect(service.findById(99999)).rejects.toThrow(NotFoundException);
    });
  });
});
