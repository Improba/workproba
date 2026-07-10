import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';

import { UserJwt } from '../entities/user-jwt.entity';

/**
 * Repository pour l'entité UserJwt
 * 
 * Fournit les méthodes de base pour interagir avec la table des utilisateurs JWT.
 * Hérite de BaseRepository qui fournit les méthodes CRUD standard :
 * - findOne, findOneById, findAndPaginate
 * - save, update, softDelete, hardDelete
 * 
 * Les requêtes personnalisées peuvent être ajoutées ici si nécessaire.
 */
@BaseCustomRepository(UserJwt)
export class UserJwtRepository extends BaseRepository<UserJwt> {} 