import { ExtractJwt, Strategy } from 'passport-jwt';
import { PassportStrategy } from '@nestjs/passport';
import { Injectable, NotFoundException } from '@nestjs/common';
import { User as User } from './entities/user.entity';
import { UserService } from './services/user.service';

/**
 * Stratégie Passport pour l'authentification JWT
 * 
 * Cette stratégie valide les tokens JWT et récupère l'utilisateur associé.
 * Elle est utilisée par le JwtAuthGuard pour protéger les routes.
 * 
 * Configuration :
 * - Extrait le token depuis le header Authorization (Bearer token)
 * - Utilise JWT_SECRET pour valider la signature
 * - Ne ignore pas l'expiration (les tokens expirés sont rejetés)
 * 
 * @extends PassportStrategy<Strategy, 'jwt-user'>
 */
@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy, 'jwt-user') {
  constructor(private readonly userService: UserService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: process.env.JWT_SECRET || 'default-secret-key',
    });
  }

  /**
   * Valide le payload JWT et retourne l'utilisateur associé
   * 
   * Cette méthode est appelée automatiquement par Passport après la validation
   * du token. Le payload contient l'ID du UserJwt dans la propriété `id`.
   * 
   * @param payload - Payload décodé du token JWT
   * @returns L'utilisateur complet associé au token
   * @throws NotFoundException si l'utilisateur n'existe pas
   */
  async validate(payload: any): Promise<User> {
    const authId = payload.id;
    const user = await this.userService.findFromUserJwtId(authId);
    if (!user) throw new NotFoundException('User not found');

    return user;
  }
}
