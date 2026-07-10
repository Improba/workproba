import { Test, TestingModule } from '@nestjs/testing';
import { BadRequestException } from '@nestjs/common';
import { UserService } from '@users/services/user.service';
import { UserRepository } from '@users/repositories/user.repository';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';
import { User, UserRoleEnum } from '@users/entities/user.entity';
import { AuthJwtUserCreatedEvent } from '@lib-improba/modules/auth-jwt/events/auth-jwt-user-created.event';

describe('UserService', () => {
  let service: UserService;

  const mockUser = {
    id: 1,
    firstname: 'John',
    roles: [UserRoleEnum.User],
  } as User;

  const mockRepository = {
    find: vi.fn(),
    findOne: vi.fn(),
    findOneById: vi.fn(),
    findCurrentUserFromJwtUsername: vi.fn(),
    findCurrentUserFromJwtId: vi.fn(),
    create: vi.fn((data: Partial<User>) => ({ id: 1, ...data })),
    save: vi.fn(async (user: User) => user),
    findByCursor: vi.fn(),
    softDelete: vi.fn(),
    findAndCount: vi.fn(),
  };

  const mockUserJwtService = {
    create: vi.fn(),
    findById: vi.fn(),
    save: vi.fn(),
    softRemove: vi.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        UserService,
        { provide: UserRepository, useValue: mockRepository },
        { provide: UserJwtService, useValue: mockUserJwtService },
      ],
    }).compile();

    service = module.get<UserService>(UserService);
    vi.clearAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('findFromUserJwtId', () => {
    it('should find user by userJwt id', async () => {
      mockRepository.findOne.mockResolvedValue(mockUser);

      const result = await service.findFromUserJwtId(10);

      expect(result).toEqual(mockUser);
      expect(mockRepository.findOne).toHaveBeenCalledWith({
        userJwt: { id: 10 },
      });
    });
  });

  describe('getAll', () => {
    it('should return all users with userJwt populated', async () => {
      mockRepository.find.mockResolvedValue([mockUser]);

      const result = await service.getAll();

      expect(result).toEqual([mockUser]);
      expect(mockRepository.find).toHaveBeenCalledWith(
        {},
        { populate: ['userJwt'] },
      );
    });
  });

  describe('findOneById', () => {
    it('should return user by id', async () => {
      mockRepository.findOne.mockResolvedValue(mockUser);

      const result = await service.findOneById(1);

      expect(result).toEqual(mockUser);
    });
  });

  describe('create', () => {
    it('should throw BadRequestException when userJwt is missing', async () => {
      await expect(
        service.create({ roles: [UserRoleEnum.User] }),
      ).rejects.toThrow(BadRequestException);
    });

    it('should create user with userJwt', async () => {
      mockUserJwtService.create.mockResolvedValue({
        id: 5,
        username: 'new@example.com',
      });
      mockUserJwtService.findById.mockResolvedValue({ id: 5 });
      mockRepository.save.mockResolvedValue(mockUser);

      const result = await service.create({
        roles: [UserRoleEnum.User],
        userJwt: { username: 'new@example.com', password: 'pass' },
      });

      expect(mockUserJwtService.create).toHaveBeenCalled();
      expect(result).toEqual(mockUser);
    });
  });

  describe('createFromAuthJwt', () => {
    it('should create user from auth jwt event', async () => {
      const event = new AuthJwtUserCreatedEvent({ id: 2 } as never);
      mockRepository.save.mockResolvedValue(mockUser);

      const result = await service.createFromAuthJwt(event);

      expect(result).toEqual(mockUser);
      expect(mockRepository.create).toHaveBeenCalled();
    });
  });

  describe('update', () => {
    it('should return undefined when user not found', async () => {
      mockRepository.findOneById.mockResolvedValue(null);

      const result = await service.update({ id: 99, firstname: 'x' });

      expect(result).toBeUndefined();
    });

    it('should update existing user', async () => {
      mockRepository.findOneById.mockResolvedValue({ ...mockUser });
      mockRepository.save.mockResolvedValue({
        ...mockUser,
        firstname: 'Jane',
      } as User);

      const result = await service.update({ id: 1, firstname: 'Jane' });

      expect(result?.firstname).toBe('Jane');
    });
  });

  describe('findWithUsername', () => {
    it('should find users by jwt username', async () => {
      mockRepository.find.mockResolvedValue([mockUser]);

      const result = await service.findWithUsername('user@test.com');

      expect(result).toEqual([mockUser]);
    });
  });

  describe('findCurrentUser', () => {
    it('should return current user from jwt username', async () => {
      mockRepository.findCurrentUserFromJwtUsername.mockResolvedValue(mockUser);

      const result = await service.findCurrentUser('user@test.com');

      expect(result).toEqual(mockUser);
    });
  });

  describe('findCurrentUserById', () => {
    it('should return current user from jwt id', async () => {
      mockRepository.findCurrentUserFromJwtId.mockResolvedValue(mockUser);

      const result = await service.findCurrentUserById(5);

      expect(result).toEqual(mockUser);
    });
  });

  describe('updateAdmin', () => {
    it('should update user as admin', async () => {
      mockRepository.findOneById.mockResolvedValue(mockUser);
      mockRepository.save.mockResolvedValue(mockUser);

      const result = await service.updateAdmin({ id: 1, firstname: 'Admin' });

      expect(result).toEqual(mockUser);
    });
  });

  describe('paginate', () => {
    it('should paginate with search query', async () => {
      mockRepository.findAndCount.mockResolvedValue([[mockUser], 1]);

      const result = await service.paginate({
        q: 'John',
        limit: 10,
        offset: 0,
      } as never);

      expect(result.results).toEqual([mockUser]);
      expect(result.count).toBe(1);
    });

    it('should paginate with role filter and username order', async () => {
      mockRepository.findAndCount.mockResolvedValue([[mockUser], 1]);

      const result = await service.paginate({
        role: UserRoleEnum.Admin,
        orderBy: 'username',
        order: 'ASC',
        limit: 5,
        offset: 0,
      } as never);

      expect(result.count).toBe(1);
    });
  });

  describe('delete', () => {
    it('should soft delete user and associated jwt', async () => {
      const userWithJwt = {
        ...mockUser,
        userJwt: { id: 2, username: 'u@test.com' },
      } as User;
      mockRepository.findOne.mockResolvedValue(userWithJwt);
      mockRepository.softDelete.mockResolvedValue(mockUser);

      const result = await service.delete(2);

      expect(mockUserJwtService.save).toHaveBeenCalled();
      expect(mockUserJwtService.softRemove).toHaveBeenCalled();
      expect(result).toEqual(mockUser);
    });

    it('should soft delete when user has no jwt', async () => {
      mockRepository.findOne.mockResolvedValue(mockUser);
      mockRepository.softDelete.mockResolvedValue(mockUser);

      const result = await service.delete(1);

      expect(result).toEqual(mockUser);
    });
  });
});
