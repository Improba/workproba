import { SetMetadata } from '@nestjs/common';

/**
 * Décorateur pour définir les rôles autorisés sur une route
 * 
 * Ce décorateur utilise SetMetadata pour stocker les rôles requis.
 * Il est utilisé par UserRolesGuard pour vérifier les permissions.
 * 
 * Utilisation :
 * ```typescript
 * @Get('admin-only')
 * @Roles(UserRoleEnum.Admin)
 * async adminRoute() { ... }
 * 
 * @Get('user-or-admin')
 * @Roles(UserRoleEnum.User, UserRoleEnum.Admin)
 * async userOrAdminRoute() { ... }
 * ```
 * 
 * Note: Si aucun rôle n'est spécifié, la route est considérée comme publique
 * (si UserRolesGuard est utilisé sans @Roles).
 * 
 * @param roles - Liste des rôles autorisés (au moins un doit correspondre)
 * @returns Décorateur de métadonnées
 */
export const Roles = (...roles: string[]) => SetMetadata('roles', roles);
