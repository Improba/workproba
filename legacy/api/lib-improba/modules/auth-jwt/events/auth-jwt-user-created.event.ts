import { UserJwt } from '../entities/user-jwt.entity';

/**
 * Événement émis lorsqu'un nouvel utilisateur JWT est créé
 * 
 * Cet événement est émis automatiquement après la création réussie d'un utilisateur
 * via UserJwtService.create(). Il permet aux listeners de réagir à la création
 * (ex: envoyer un email de bienvenue, créer des données associées, etc.).
 * 
 * Événement écoutable via : @OnEvent('authJwt.userCreated')
 */
export class AuthJwtUserCreatedEvent {
  /** L'utilisateur qui vient d'être créé */
  user: UserJwt;

  constructor(user: UserJwt) {
    this.user = user;
  }
}
