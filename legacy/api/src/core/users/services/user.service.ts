import {
  Injectable,
  BadRequestException,
  NotFoundException,
  InternalServerErrorException,
} from '@nestjs/common';

import { BaseService } from '@lib-improba/base/base.service';
import { User } from '../entities/user.entity';
import { UserRepository } from '../repositories/user.repository';
import { UserRoleEnum } from '../entities/user.entity';
import { IPaginationOptions } from '@lib-improba/base/base.repository';
import { AuthJwtUserCreatedEvent } from '@lib-improba/modules/auth-jwt/events/auth-jwt-user-created.event';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';
import {
  UserCreateForAdminDto,
  AdminUserUpdateDto,
  PaginateUserDTO,
} from '../controllers/admin/admin-user.controller';
import { UserUpdateDto } from '../controllers/user.controller';
import {
  FilterQuery,
  LoadStrategy,
  OrderDefinition,
  wrap,
} from '@mikro-orm/core';

/**
 * Service de gestion des utilisateurs
 * 
 * Ce service étend BaseService et fournit toutes les opérations CRUD pour les utilisateurs.
 * Il gère également la création d'utilisateurs depuis les événements AuthJwt et la pagination.
 * 
 * @extends BaseService<User, UserRepository>
 */
@Injectable()
export class UserService extends BaseService<User, UserRepository> {
  constructor(
    private readonly repository: UserRepository,
    private readonly userJwtService: UserJwtService,
  ) {
    super(repository);
  }

  /**
   * Trouve un utilisateur par l'ID de son UserJwt associé
   * 
   * @param id - ID du UserJwt
   * @returns L'utilisateur trouvé ou null
   */
  async findFromUserJwtId(id: number): Promise<User | null> {
    return await this.repository.findOne({
      userJwt: {
        id: id,
      },
    });
  }

  /**
   * Récupère tous les utilisateurs avec leurs informations JWT
   * 
   * @returns Liste complète de tous les utilisateurs
   */
  async getAll(): Promise<User[]> {
    const users = await this.repository.find(
      {},
      {
        populate: ['userJwt'] as const,
      },
    );

    return users;
  }

  /**
   * Trouve un utilisateur par son ID avec ses informations JWT
   * 
   * @param id - ID de l'utilisateur
   * @returns L'utilisateur trouvé ou null
   */
  override async findOneById(id: number): Promise<User | null> {
    const user = await this.repository.findOne(
      {
        id,
      },
      {
        populate: ['userJwt'] as const,
      },
    );

    return user;
  }

  /**
   * Trouve des utilisateurs par leur nom d'utilisateur JWT
   * 
   * @param username - Nom d'utilisateur à rechercher
   * @returns Liste des utilisateurs correspondants ou undefined
   */
  async findWithUsername(
    username: string,
  ): Promise<Partial<User[]> | undefined> {
    const users = await this.repository.find(
      {
        userJwt: {
          username: username,
        },
      },
      {
        populate: ['userJwt'] as const,
      },
    );

    return users;
  }

  /**
   * Trouve l'utilisateur actuel par son nom d'utilisateur JWT
   * 
   * @param username - Nom d'utilisateur JWT
   * @returns L'utilisateur trouvé
   * @throws NotFoundException si l'utilisateur n'existe pas
   */
  async findCurrentUser(username: string): Promise<User> {
    const user = await this.repository.findCurrentUserFromJwtUsername(username);
    return user;
  }

  /**
   * Trouve l'utilisateur actuel par l'ID de son UserJwt
   * 
   * @param id - ID du UserJwt
   * @returns L'utilisateur trouvé
   * @throws NotFoundException si l'utilisateur n'existe pas
   */
  async findCurrentUserById(id: number): Promise<User> {
    const user = await this.repository.findCurrentUserFromJwtId(id);
    return user;
  }

  /**
   * Crée un nouvel utilisateur avec ses informations JWT
   * 
   * Cette méthode est utilisée par les administrateurs pour créer des utilisateurs.
   * Elle crée d'abord le UserJwt, puis l'utilisateur associé.
   * 
   * @param options - DTO contenant les informations de l'utilisateur et du UserJwt
   * @returns L'utilisateur créé
   * @throws BadRequestException si userJwt n'est pas fourni
   */
  async create(options: UserCreateForAdminDto): Promise<User> {
    // Créer d'abord le UserJwt
    const userJwtDto = options.userJwt;
    if (!userJwtDto) throw new BadRequestException();
    const userJwt = await this.userJwtService.create(
      {
        ...userJwtDto,
        activated: true,
      },
      false, // Ne pas émettre l'événement userCreated pour éviter une double création
    );

    // Supprimer les infos JWT du DTO avant de créer l'utilisateur
    delete options.userJwt;

    // Créer l'utilisateur avec les valeurs par défaut
    const newUser = this.repository.create({
      ...options,
      userJwt: undefined,
      resetPasswordOngoing: false,
      roles: options.roles ?? [UserRoleEnum.User],
      preferDarkTheme: true,
      isAdmin: options.roles?.includes(UserRoleEnum.Admin) ?? false,
    });
    // Associer le UserJwt créé
    newUser.userJwt = await this.userJwtService.findById(userJwt.id);
    const newUserSaved = await this.repository.save(newUser);

    return newUserSaved;
  }

  /**
   * Crée un utilisateur depuis un événement AuthJwtUserCreatedEvent
   * 
   * Cette méthode est appelée automatiquement par le listener UserCreatedListener
   * lorsqu'un UserJwt est créé via le module auth-jwt.
   * 
   * @param event - Événement contenant le UserJwt créé
   * @returns L'utilisateur créé avec les valeurs par défaut
   */
  async createFromAuthJwt(event: AuthJwtUserCreatedEvent): Promise<User> {
    const newUser = this.repository.create({
      resetPasswordOngoing: false,
      roles: [UserRoleEnum.User],
      preferDarkTheme: true,
      isAdmin: false,
    });
    newUser.userJwt = event.user;

    const newUserSaved = await this.repository.save(newUser);

    return newUserSaved;
  }

  /**
   * Met à jour un utilisateur (méthode standard)
   * 
   * Fusionne les données existantes avec les nouvelles données fournies.
   * 
   * @param dtoToBeUpdated - DTO contenant l'ID et les champs à mettre à jour
   * @returns L'utilisateur mis à jour ou undefined si non trouvé
   */
  async update(dtoToBeUpdated: UserUpdateDto): Promise<User | undefined> {
    const existingDto = await super.findOneById(dtoToBeUpdated.id);

    if (!existingDto) return;

    const updatedDto = {
      ...existingDto,
      ...dtoToBeUpdated,
    };

    const savedDto = await this.repository.save(updatedDto);
    return savedDto;
  }

  /**
   * Met à jour un utilisateur (méthode admin)
   * 
   * Cette méthode permet aux administrateurs de mettre à jour tous les champs,
   * y compris les rôles.
   * 
   * @param dtoToBeUpdated - DTO contenant l'ID et les champs à mettre à jour
   * @returns L'utilisateur mis à jour ou undefined si non trouvé
   */
  async updateAdmin(
    dtoToBeUpdated: AdminUserUpdateDto,
  ): Promise<User | undefined> {
    const existingDto = await super.findOneById(dtoToBeUpdated.id);

    if (!existingDto) return;

    const savedDto = await this.repository.save(dtoToBeUpdated);
    return savedDto;
  }

  /**
   * Supprime un utilisateur (soft delete)
   * 
   * Cette méthode effectue une suppression douce :
   * 1. Renomme le username du UserJwt associé pour éviter les conflits
   * 2. Supprime doucement le UserJwt
   * 3. Supprime doucement l'utilisateur
   * 
   * Note: Le paramètre `id` correspond à l'ID du UserJwt, pas de l'utilisateur.
   * 
   * @param id - ID du UserJwt de l'utilisateur à supprimer
   * @returns L'utilisateur supprimé ou null si non trouvé
   */
  override async delete(id: number): Promise<User | null> {
    const userToBeDeleted = await this.repository.findOne(
      {
        userJwt: {
          id: id,
        },
      },
      {
        populate: ['userJwt'] as const,
      },
    );
    if (userToBeDeleted && userToBeDeleted.userJwt) {
      // Renommer le username pour éviter les conflits lors de futures créations
      userToBeDeleted.userJwt.username = `softDeleted_${userToBeDeleted?.userJwt.id}_${userToBeDeleted?.userJwt.username}`;
      await this.userJwtService.save(userToBeDeleted.userJwt);
      await this.userJwtService.softRemove(userToBeDeleted.userJwt);
    }
    // Effectuer la suppression douce de l'utilisateur
    return await super.delete(id);
  }

  /**
   * Récupère une liste paginée d'utilisateurs avec filtres et tri.
   *
   * Cette méthode permet de rechercher et paginer les utilisateurs en appliquant
   * des filtres optionnels (recherche par nom, username, role) et un tri personnalisé.
   *
   * @param dto - Options de pagination et filtrage
   *
   * @returns Objet contenant les résultats paginés et le nombre total
   *
   * @example
   * // Récupérer les 10 premiers administrateurs triés par nom
   * const page1 = await service.paginate({
   *   limit: 10,
   *   offset: 0,
   *   orderBy: 'firstname',
   *   order: QueryOrder.ASC,
   *   role: UserRoleEnum.Admin,
   * });
   * // { results: [...], count: 42 }
   *
   * @example
   * // Rechercher des utilisateurs contenant "Jean"
   * const search = await service.paginate({
   *   q: 'Jean',
   *   populate: ['userJwt'],
   * });
   */
  async paginate(dto: PaginateUserDTO) {
    const where: FilterQuery<User> = {};

    if (dto.q) {
      where.$or = [
        {
          userJwt: {
            username: {
              $ilike: `%${dto.q}%`,
            },
          },
        },
        {
          firstname: {
            $ilike: `%${dto.q}%`,
          },
        },
        {
          lastname: {
            $ilike: `%${dto.q}%`,
          },
        },
      ];
    }

    if (dto.role) {
      where.roles = dto.role;
    }

    let orderBy: OrderDefinition<User> = {
      [dto.orderBy || 'id']: dto.order,
    };

    // @ts-ignore
    // The next comparison is intentional
    if (dto.orderBy === 'username') {
      orderBy = {
        userJwt: {
          username: dto.order,
        },
      };
    }

    const [results, count] = await this.repository.findAndCount(where, {
      limit: dto.limit,
      offset: dto.offset,
      orderBy,
      populate: dto.populate,
    });

    return {
      results,
      count,
    };
  }
}
