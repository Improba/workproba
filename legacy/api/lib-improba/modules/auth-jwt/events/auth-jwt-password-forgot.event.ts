import { UserJwt } from '../entities/user-jwt.entity';

/**
 * Événement émis lorsqu'un utilisateur demande la réinitialisation de son mot de passe
 * 
 * Cet événement est émis automatiquement après la génération d'un token de réinitialisation
 * via UserJwtService.sendMailForNewPassword(). Il permet aux listeners de réagir à la demande
 * (ex: envoyer un email personnalisé, logger l'événement, etc.).
 * 
 * Note: L'envoi d'email via SendGrid est géré directement dans le service,
 * mais cet événement permet d'ajouter des traitements supplémentaires.
 * 
 * Événement écoutable via : @OnEvent('authJwt.passwordForgot')
 */
export class AuthJwtPasswordForgotEvent {
  /** L'utilisateur qui a demandé la réinitialisation de mot de passe */
  user: UserJwt;

  constructor(user: UserJwt) {
    this.user = user;
  }
}
