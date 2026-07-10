import {
  Injectable,
  CanActivate,
  ExecutionContext,
  BadRequestException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';

import { UserRoleEnum } from '../entities/user.entity';
import { UserService } from '@core/users/services/user.service';

/**
 * Guard pour la gestion des rôles et permissions
 * 
 * Ce guard vérifie que l'utilisateur authentifié possède les rôles requis
 * pour accéder à la route. Il doit être utilisé après JwtAuthGuard.
 * 
 * Règles de permission :
 * - Si aucun rôle n'est spécifié (@Roles()), la route est publique
 * - Les administrateurs ont accès à toutes les routes
 * - Un utilisateur doit avoir au moins un des rôles autorisés
 * 
 * Utilisation :
 * ```typescript
 * @UseGuards(JwtAuthGuard, UserRolesGuard)
 * @Roles(UserRoleEnum.Admin)
 * ```
 * 
 * @implements CanActivate
 */
@Injectable()
export class UserRolesGuard implements CanActivate {
  constructor(
    private readonly reflector: Reflector,
    private readonly userService: UserService,
  ) {}

  /**
   * Vérifie si l'utilisateur peut accéder à la route
   * 
   * @param context - Contexte d'exécution de la requête
   * @returns true si l'utilisateur a les permissions, false sinon
   */
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const authorizedRoles = this.reflector.getAllAndOverride<string[]>(
      'roles',
      [context.getHandler(), context.getClass()],
    );
    if (!authorizedRoles) return true;
    const request = context.switchToHttp().getRequest();

    // request.user contient l'utilisateur injecté par JwtAuthGuard
    const roles = request.user.roles;

    return this.matchRoles(authorizedRoles, roles);
  }

  /**
   * Vérifie si les rôles de l'utilisateur correspondent aux rôles autorisés
   * 
   * @param authorizedRoles - Liste des rôles autorisés pour la route
   * @param userRoles - Liste des rôles de l'utilisateur
   * @returns true si l'utilisateur a les permissions, false sinon
   */
  private matchRoles(
    authorizedRoles: string[],
    userRoles: string[] | undefined,
  ): boolean {
    if (!userRoles || userRoles.length === 0) return false;
    // Les administrateurs ont accès à toutes les routes
    if (userRoles.includes(UserRoleEnum.Admin)) return true;
    // L'utilisateur doit avoir au moins un des rôles autorisés
    return authorizedRoles.some((authorizedRole) =>
      userRoles.includes(authorizedRole),
    );
  }
}
