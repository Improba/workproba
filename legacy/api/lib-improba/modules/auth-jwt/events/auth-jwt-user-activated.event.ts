import { UserJwt } from '../entities/user-jwt.entity';

/**
 * Événement émis lorsqu'un compte utilisateur JWT est activé
 * 
 * Cet événement est émis automatiquement après l'activation réussie d'un compte
 * via UserJwtService.activate(). Il permet aux listeners de réagir à l'activation
 * (ex: envoyer un email de confirmation, activer des fonctionnalités, etc.).
 * 
 * Événement écoutable via : @OnEvent('authJwt.userActivated')
 */
export class AuthJwtUserActivatedEvent {
  /** L'utilisateur dont le compte vient d'être activé */
  user: UserJwt;

  constructor(user: UserJwt) {
    this.user = user;
  }
}
