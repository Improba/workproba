import { NotFoundException } from '@nestjs/common';
import { User } from '../entities/user.entity';
import {
  BaseRepository,
} from '@lib-improba/base/base.repository';

import { BaseCustomRepository } from '@lib-improba/decorators';

/**
 * Repository pour l'entité User
 * 
 * Ce repository étend BaseRepository et fournit des méthodes spécifiques
 * pour rechercher des utilisateurs par leurs informations JWT associées.
 * 
 * @extends BaseRepository<User>
 */
@BaseCustomRepository(User)
export class UserRepository extends BaseRepository<User> {
  /**
   * Trouve un utilisateur par le nom d'utilisateur JWT associé
   * 
   * Cette méthode est utilisée pour récupérer l'utilisateur complet depuis
   * un nom d'utilisateur JWT, notamment lors de l'authentification.
   * 
   * @param username - Nom d'utilisateur JWT
   * @returns L'utilisateur trouvé avec ses informations JWT populées
   * @throws NotFoundException si aucun utilisateur n'est trouvé
   */
  async findCurrentUserFromJwtUsername(username: string): Promise<User> {
    const user = await this.findOne({
      userJwt: {
        username: username,
      }
    }, {
      populate: ['userJwt'] as const
    });
    if (!user) {
      throw new NotFoundException(`No user with username: ${username}`);
    }

    return user;
  }

  /**
   * Trouve un utilisateur par l'ID du UserJwt associé
   * 
   * Cette méthode est utilisée pour récupérer l'utilisateur complet depuis
   * un ID de UserJwt, notamment lors de la validation du token JWT.
   * 
   * @param id - ID du UserJwt
   * @returns L'utilisateur trouvé avec ses informations JWT populées
   * @throws NotFoundException si aucun utilisateur n'est trouvé
   */
  async findCurrentUserFromJwtId(id: number): Promise<User> {
    const user = await this.findOne({
      userJwt: {
        id: id,
      }
    }, {
      populate: ['userJwt'] as const
    });
    if (!user) {
      throw new NotFoundException(`No user with id: ${id}`);
    }

    return user;
  }
}
