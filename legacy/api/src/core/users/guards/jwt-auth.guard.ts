import { Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

/**
 * Guard pour l'authentification JWT
 * 
 * Ce guard utilise la stratégie Passport 'jwt-user' pour valider les tokens JWT.
 * Il doit être utilisé en combinaison avec UserRolesGuard pour gérer les permissions.
 * 
 * Utilisation :
 * ```typescript
 * @UseGuards(JwtAuthGuard, UserRolesGuard)
 * @Roles(UserRoleEnum.User)
 * ```
 * 
 * @extends AuthGuard<'jwt-user'>
 */
@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt-user') {}
