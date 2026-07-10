import { BaseEntity } from '@lib-improba/base/base.entity';
import { Entity, Property, Unique } from '@mikro-orm/decorators/legacy';

// Import conditionnel de ApiProperty pour éviter les erreurs lors des migrations CLI
let ApiProperty: any;
try {
  ApiProperty = require('@nestjs/swagger').ApiProperty;
} catch (e) {
  // Si @nestjs/swagger n'est pas disponible (ex: migrations CLI), utiliser un décorateur vide
  ApiProperty = () => () => {};
}

/**
 * Entité UserJwt - Représente un utilisateur avec authentification JWT
 * 
 * Cette entité stocke les informations d'authentification d'un utilisateur :
 * - Identifiants de connexion (username, password hashé)
 * - Statut d'activation du compte
 * - Tokens pour l'activation et la réinitialisation de mot de passe
 * 
 * Hérite de BaseEntity qui fournit : id, createdAt, updatedAt, deletedAt (soft delete)
 */
@Entity()
export class UserJwt extends BaseEntity {
  /**
   * Nom d'utilisateur unique utilisé pour la connexion
   * Peut être un email ou un identifiant personnalisé
   */
  @ApiProperty({ description: 'Nom d\'utilisateur unique (peut être un email)', example: 'john.doe@example.com' })
  @Property({ type: 'string' })
  @Unique()
  username!: string;

  /**
   * Mot de passe hashé avec bcrypt (10 rounds)
   * Le champ est masqué dans les sérialisations JSON (hidden: true)
   */
  @ApiProperty({ description: 'Mot de passe hashé (masqué dans les réponses)', example: '***', writeOnly: true, readOnly: false })
  @Property({ type: 'string', hidden: true })
  password!: string;

  /**
   * Statut d'activation du compte
   * Par défaut à false. Un compte non activé ne peut pas se connecter.
   */
  @ApiProperty({ description: 'Statut d\'activation du compte', example: false, default: false })
  @Property({ type: 'boolean', default: false })
  activated = false;

  /**
   * Token unique pour l'activation du compte
   * Généré lors de la création du compte (UUID v4)
   * Masqué dans les sérialisations JSON (hidden: true)
   */
  @ApiProperty({ description: 'Token d\'activation (masqué dans les réponses)', example: null, nullable: true, writeOnly: true, readOnly: false })
  @Property({ type: 'string', nullable: true, hidden: true })
  activationToken!: string | null;

  /**
   * Date de la dernière demande de réinitialisation de mot de passe
   * Utilisé pour limiter la fréquence des demandes (1 toutes les 10 minutes)
   */
  @ApiProperty({ description: 'Date de la dernière demande de réinitialisation de mot de passe', example: null, nullable: true, type: Date, required: false })
  @Property({ type: 'timestamp', nullable: true })
  lastResetPasswordAt!: Date | null;

  /**
   * Token unique pour la réinitialisation de mot de passe
   * Généré lors d'une demande de réinitialisation (UUID v4)
   * Masqué dans les sérialisations JSON (hidden: true)
   * Supprimé après utilisation réussie
   */
  @ApiProperty({ description: 'Token de réinitialisation de mot de passe (masqué dans les réponses)', example: null, nullable: true, writeOnly: true, readOnly: false })
  @Property({ type: 'string', nullable: true, hidden: true })
  forgetPasswordToken!: string | null;
}
