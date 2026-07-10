import { UserJwt } from '../entities/user-jwt.entity';

/**
 * Événement émis lorsqu'un utilisateur JWT est supprimé (soft delete)
 * 
 * Cet événement peut être émis manuellement lors de la suppression d'un utilisateur
 * via UserJwtService.softRemove(). Il permet aux listeners de réagir à la suppression
 * (ex: nettoyer les données associées, envoyer une notification, etc.).
 * 
 * Note: Cet événement n'est pas émis automatiquement par défaut.
 * Il doit être émis manuellement si nécessaire lors de la suppression.
 * 
 * Événement écoutable via : @OnEvent('authJwt.userDeleted')
 */
export class AuthJwtUserDeletedEvent {
  /** L'utilisateur qui vient d'être supprimé */
  user: UserJwt;

  constructor(user: UserJwt) {
    this.user = user;
  }
}
