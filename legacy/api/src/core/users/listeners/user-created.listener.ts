import { Injectable, InternalServerErrorException } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { AuthJwtUserCreatedEvent } from '@lib-improba/modules/auth-jwt/events/auth-jwt-user-created.event';
import { UserService } from '../services/user.service';

/**
 * Listener pour les événements de création d'utilisateurs JWT
 * 
 * Ce listener écoute l'événement 'authJwt.userCreated' émis par le module auth-jwt
 * lorsqu'un nouveau UserJwt est créé. Il crée automatiquement un User associé.
 * 
 * Configuration :
 * - async: true - Permet l'utilisation de await emitAsync()
 * - promisify: true - Convertit le handler en promesse
 * 
 * @see AuthJwtUserCreatedEvent pour la structure de l'événement
 * @see UserService.createFromAuthJwt pour la création de l'utilisateur
 */
@Injectable()
export class UserCreatedListener {
  constructor(private service: UserService) {}

  /**
   * Gère l'événement de création d'un UserJwt
   * 
   * Cette méthode est appelée automatiquement lorsqu'un UserJwt est créé
   * via le module auth-jwt. Elle crée un User associé avec les valeurs par défaut.
   * 
   * @param event - Événement contenant le UserJwt créé
   * @throws InternalServerErrorException si la création échoue
   */
  @OnEvent('authJwt.userCreated', {
    // Ces options sont requises pour gérer correctement les événements asynchrones
    // (utiliser await emitAsync lors de l'émission)
    async: true,
    promisify: true,
  })
  async handleUserCreatedEvent(event: AuthJwtUserCreatedEvent) {
    try {
      // Créer un User associé au UserJwt créé
      await this.service.createFromAuthJwt(event);
    } catch (err) {
      throw new InternalServerErrorException('Create from auth-jwt error');
    }
  }
}
