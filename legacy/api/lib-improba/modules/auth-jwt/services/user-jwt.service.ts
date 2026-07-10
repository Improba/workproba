import {
  Injectable,
  NotFoundException,
  BadRequestException,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { ApiProperty } from '@nestjs/swagger';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { JwtService } from '@nestjs/jwt';
import { v4 as uuidv4 } from 'uuid';
import * as bcrypt from 'bcrypt';
import * as sgMail from '@sendgrid/mail';

import { UserJwt } from '../entities/user-jwt.entity';
import { UserJwtCreateDto } from '../controllers/auth-jwt.controller';
import { UserJwtRepository } from '../repositories/user-jwt.repository';

import { AuthJwtPasswordForgotEvent } from '../events/auth-jwt-password-forgot.event';
import { AuthJwtUserCreatedEvent } from '../events/auth-jwt-user-created.event';
import { AuthJwtUserActivatedEvent } from '../events/auth-jwt-user-activated.event';
import { InjectRepository } from '@mikro-orm/nestjs';
import { ConfigService } from '@nestjs/config';

/**
 * Classe de réponse pour les opérations liées aux tokens
 */
export class TokenResponse {
  @ApiProperty({ description: 'Token JWT généré', example: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' })
  token!: string;

  @ApiProperty({ description: 'Message de réponse', example: 'Token généré avec succès' })
  message!: string;

  @ApiProperty({ description: 'Liste des erreurs éventuelles', type: [String], example: [] })
  errors!: string[];
}

/**
 * Classe de réponse pour les opérations génériques avec statut de succès
 */
export class SuccessResponse {
  @ApiProperty({ description: 'Indique si l\'opération a réussi', example: true })
  success!: boolean;

  @ApiProperty({ description: 'Message de réponse', example: 'Opération réussie' })
  message!: string;

  @ApiProperty({ description: 'Liste des erreurs éventuelles', type: [String], example: [] })
  errors!: string[];

  @ApiProperty({ description: 'Résultat spécifique de l\'opération', required: false })
  output?: any; // Retourne un résultat spécifique
}

/**
 * Service de gestion des utilisateurs JWT
 * Fournit des méthodes pour l'authentification, l'enregistrement et la gestion des utilisateurs
 */
@Injectable()
export class UserJwtService {
  constructor(
    private readonly userJwtRepository: UserJwtRepository,
    private readonly eventEmitter: EventEmitter2,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
  ) {}

  /**
   * Crée un nouvel utilisateur JWT
   * @param userJwtCreateDto DTO contenant les informations de création d'utilisateur
   * @param emitUserCreateSignal Indique si un événement doit être émis après la création
   * @returns L'ID et le nom d'utilisateur du UserJwt créé
   */
  async create(
    userJwtCreateDto: UserJwtCreateDto,
    emitUserCreateSignal = true,
  ): Promise<Pick<UserJwt, 'id' | 'username'>> {
    // Hachage du mot de passe avec bcrypt
    const encryptedPassword = await bcrypt.hash(userJwtCreateDto.password, 10);

    // Préparation des données pour la création
    const userJwtToBeCreated = {
      activationToken: uuidv4(),
      password: encryptedPassword,
      username: userJwtCreateDto.username,
      activated: true, // Par défaut activé, peut être modifié selon les besoins
    };

    // Création et sauvegarde de l'entité
    const userJwtToCreate = this.userJwtRepository.create(userJwtToBeCreated);
    const createdUserJwt = await this.userJwtRepository.save(userJwtToCreate);

    // Émission d'un événement de création si demandé
    if (emitUserCreateSignal) {
      await this.eventEmitter.emitAsync(
        'authJwt.userCreated',
        new AuthJwtUserCreatedEvent(createdUserJwt),
      );
    }

    // Retourne uniquement l'ID et le nom d'utilisateur
    return {
      id: createdUserJwt.id,
      username: createdUserJwt.username,
    };
  }

  /**
   * Génère un token JWT pour l'authentification
   * @param userJwt L'utilisateur pour lequel créer le token
   * @returns Token JWT signé
   */
  login(userJwt: UserJwt): string {
    const payload = { id: userJwt.id, username: userJwt.username };
    const expiresIn = this.configService.get<string>('JWT_EXPIRES_IN', '1h');

    return this.jwtService.sign(payload, {
      expiresIn,
    } as any);
  }

  /**
   * Crée un nouveau token JWT à partir d'un token existant valide
   * 
   * Vérifie que le token fourni est valide, puis génère un nouveau token avec les mêmes
   * informations utilisateur mais une nouvelle date d'expiration.
   * 
   * @param token Token JWT existant à rafraîchir
   * @returns Nouveau token JWT ou null si le token d'origine est invalide ou expiré
   */
  createNewTokenFromPreviousOne(token: string): string | null {
    try {
      // Vérification de la validité du token (signature et expiration)
      if (!this.jwtService.verify(token)) {
        return null;
      }

      // Décodage du payload du token
      const payload = this.jwtService.decode(token);
      if (!payload || typeof payload !== 'object') {
        return null;
      }

      // Typage explicite du payload (évite l'utilisation de 'any')
      interface JwtPayload {
        id: number;
        username: string;
        iat?: number;
        exp?: number;
      }

      const typedPayload = payload as JwtPayload;

      // Vérification que les champs nécessaires sont présents
      if (!typedPayload.id || !typedPayload.username) {
        return null;
      }

      // Génération d'un nouveau token avec la même expiration configurée
      const expiresIn = this.configService.get<string>(
        'JWT_EXPIRES_IN',
        '1h',
      );

      return this.jwtService.sign(
        {
          id: typedPayload.id,
          username: typedPayload.username,
        },
        {
          expiresIn,
        } as any,
      );
    } catch (error) {
      // En cas d'erreur (token invalide, malformé, etc.), retourne null
      return null;
    }
  }

  /**
   * Active un compte utilisateur avec le token d'activation
   * 
   * Recherche un utilisateur par son token d'activation et active son compte.
   * Si le compte est déjà activé, retourne un succès sans modification.
   * Émet un événement 'authJwt.userActivated' après activation réussie.
   * 
   * @param activationToken Token d'activation unique généré lors de la création du compte
   * @returns Résultat de l'opération d'activation avec statut de succès
   * @throws NotFoundException si aucun utilisateur n'est trouvé avec ce token
   */
  async activate(activationToken: string): Promise<SuccessResponse> {
    const result = new SuccessResponse();
    result.success = false;
    result.message = 'Échec de l\'activation';

    try {
      // Recherche de l'utilisateur par son token d'activation
      const userJwt = await this.userJwtRepository.findOne({
        activationToken,
      });

      if (!userJwt) {
        throw new NotFoundException('Token d\'activation invalide');
      }

      // Si déjà activé, retourne succès avec message approprié
      if (userJwt.activated === true) {
        result.success = true;
        result.message = 'Compte déjà activé';
        result.errors = [];
        return result;
      }

      // Activation de l'utilisateur
      userJwt.activated = true;
      await this.userJwtRepository.save(userJwt);
      result.success = true;
      result.message = 'Compte activé avec succès';
      result.errors = [];

      // Émission d'un événement d'activation pour notifier les listeners
      await this.eventEmitter.emitAsync(
        'authJwt.userActivated',
        new AuthJwtUserActivatedEvent(userJwt),
      );

      return result;
    } catch (error) {
      // Gestion des erreurs avec typage explicite
      const errorMessage = error instanceof Error ? error.message : 'Erreur inconnue';
      const errorCode = (error as { code?: string }).code || 'UNKNOWN';
      result.errors = [`${errorCode} - ${errorMessage}`];
      return result;
    }
  }

  /**
   * Recherche un utilisateur par son nom d'utilisateur
   * @param username Nom d'utilisateur à rechercher
   * @returns L'utilisateur trouvé ou null
   */
  async findByUsername(username: string): Promise<UserJwt | null> {
    const userJwt = await this.userJwtRepository
      .createQueryBuilder()
      .andWhere('LOWER(username) = LOWER(?)', [username])
      .andWhere('activated = true')
      .getSingleResult();

    return userJwt;
  }

  /**
   * Authentifie un utilisateur par son nom d'utilisateur et mot de passe
   * 
   * Recherche un utilisateur par son username et vérifie le mot de passe avec bcrypt.
   * Retourne l'utilisateur complet si l'authentification réussit.
   * 
   * @param username Nom d'utilisateur ou email de l'utilisateur
   * @param password Mot de passe en clair à vérifier
   * @returns L'utilisateur authentifié avec toutes ses propriétés
   * @throws BadRequestException si les identifiants sont incorrects ou si l'utilisateur n'existe pas
   */
  async findByUsernamePassword(
    username: string,
    password: string,
  ): Promise<UserJwt> {
    // Recherche de l'utilisateur avec uniquement les champs nécessaires pour l'authentification
    // (optimisation : ne charge pas tous les champs inutiles)
    const userJwt = await this.userJwtRepository.findOne(
      {
        username: username,
      },
      {
        fields: ['username', 'id', 'password', 'activated'] as Array<
          keyof UserJwt
        >,
      },
    );

    // Vérification que l'utilisateur existe et que le mot de passe correspond
    if (
      userJwt?.password &&
      (await bcrypt.compare(password, userJwt.password))
    ) {
      // Récupération de l'utilisateur complet avec toutes ses propriétés
      const fullUserJwt = await this.userJwtRepository.findOne({
        id: userJwt.id,
      });
      
      if (!fullUserJwt) {
        throw new HttpException(
          'Utilisateur non trouvé',
          HttpStatus.NOT_FOUND,
        );
      }
      
      return fullUserJwt;
    }

    // Si l'utilisateur n'existe pas ou le mot de passe est incorrect, lance une exception
    throw new BadRequestException('Identifiants incorrects');
  }

  /**
   * Récupère un utilisateur par son ID
   * @param id ID de l'utilisateur
   * @returns L'utilisateur trouvé
   * @throws NotFoundException si l'utilisateur n'est pas trouvé
   */
  async findById(id: number): Promise<UserJwt> {
    const userJwt = await this.userJwtRepository.findOneById(id);
    if (!userJwt) {
      throw new NotFoundException();
    }

    return userJwt;
  }

  /**
   * Envoie un email pour réinitialiser le mot de passe
   * 
   * Recherche un utilisateur par son email (username), génère un token de réinitialisation
   * unique et envoie un email avec un lien de réinitialisation via SendGrid.
   * 
   * Limitations :
   * - Un email ne peut être envoyé que toutes les 10 minutes par utilisateur
   * - L'envoi d'email nécessite la configuration de SENDGRID_API_KEY
   * 
   * Émet un événement 'authJwt.passwordForgot' après génération du token.
   * 
   * @param email Email de l'utilisateur (correspond au champ username)
   * @returns L'utilisateur dont le mot de passe va être réinitialisé
   * @throws BadRequestException si l'utilisateur n'est pas trouvé ou si un email a déjà été envoyé récemment (< 10 minutes)
   */
  async sendMailForNewPassword(email: string): Promise<UserJwt> {
    // Recherche de l'utilisateur par email (le username peut être un email)
    const userJwt = await this.userJwtRepository.findOne(
      {
        username: email,
      },
      {
        fields: [
          'id',
          'username',
          'forgetPasswordToken',
          'lastResetPasswordAt',
          'activated',
        ] as Array<keyof UserJwt>,
      },
    );

    if (!userJwt) {
      throw new BadRequestException('Utilisateur non trouvé');
    }

    // Vérification du délai entre les demandes de réinitialisation (10 minutes)
    const now = new Date();
    const delayBetweenRequests = 1000 * 60 * 10; // 10 minutes en millisecondes
    const lastResetPasswordAt = userJwt.lastResetPasswordAt;

    if (
      lastResetPasswordAt &&
      lastResetPasswordAt.getTime() > now.getTime() - delayBetweenRequests
    ) {
      throw new BadRequestException(
        'Un email de réinitialisation a déjà été envoyé récemment. Veuillez attendre 10 minutes.',
      );
    }

    // Génération d'un token de réinitialisation unique (UUID v4)
    // L'UUID garantit l'unicité et la sécurité du token
    userJwt.forgetPasswordToken = uuidv4();
    userJwt.lastResetPasswordAt = new Date();
    await this.userJwtRepository.save(userJwt);

    // Émission d'un événement de mot de passe oublié pour notifier les listeners
    await this.eventEmitter.emitAsync(
      'authJwt.passwordForgot',
      new AuthJwtPasswordForgotEvent(userJwt),
    );

    // Construction de l'URL de réinitialisation
    const frontendUrl = this.configService.get<string>('FRONTEND_URL', '');
    const resetUrl = `${frontendUrl}/auth/password-reset?token=${userJwt.forgetPasswordToken}`;

    // Envoi d'email avec SendGrid si la clé API est configurée
    const sgKey = this.configService.get<string>('SENDGRID_API_KEY');
    if (sgKey) {
      const emailFrom = this.configService.get<string>('EMAIL_FROM');
      const appName = this.configService.get<string>('APP_NAME', 'Application');

      if (!emailFrom) {
        console.error('EMAIL_FROM n\'est pas configuré');
        return userJwt;
      }

      sgMail.setApiKey(sgKey);
      const msg = {
        to: email,
        from: emailFrom, // Adresse email vérifiée dans SendGrid
        subject: `${appName} - Réinitialisation de mot de passe`,
        text: `Cliquez sur ce lien pour réinitialiser votre mot de passe : ${resetUrl}`,
        html: `<a href="${resetUrl}">Cliquez ici</a> pour réinitialiser votre mot de passe.`,
      };

      try {
        await sgMail.send(msg);
      } catch (error) {
        // Log de l'erreur sans interrompre le processus
        console.error('Erreur lors de l\'envoi de l\'email SendGrid:', error);
        if ((error as { response?: { body?: unknown } }).response?.body) {
          console.error(
            'Détails de l\'erreur SendGrid:',
            (error as { response: { body: unknown } }).response.body,
          );
        }
      }
    } else {
      console.warn(
        'SENDGRID_API_KEY n\'est pas configuré. L\'email de réinitialisation ne sera pas envoyé.',
      );
    }

    return userJwt;
  }

  /**
   * Recherche un utilisateur par son token de récupération
   * @param token Token de récupération de mot de passe
   * @returns L'utilisateur associé au token
   * @throws BadRequestException si l'utilisateur n'est pas trouvé
   */
  async findByRecuperationToken(token: string): Promise<UserJwt> {
    const userJwt = await this.userJwtRepository.findOne({
      forgetPasswordToken: token,
    });

    if (!userJwt) {
      throw new BadRequestException('Token de réinitialisation invalide');
    }

    return userJwt;
  }

  /**
   * Change le mot de passe d'un utilisateur via un token de récupération
   * 
   * Recherche un utilisateur par son token de récupération, change son mot de passe
   * et supprime le token de récupération pour éviter sa réutilisation.
   * 
   * @param token Token de récupération unique reçu par email
   * @param password Nouveau mot de passe en clair (sera hashé avec bcrypt)
   * @returns Résultat de l'opération avec l'utilisateur mis à jour
   * @throws BadRequestException si aucun utilisateur n'est trouvé avec ce token
   */
  async changePasswordUser(
    token: string,
    password: string,
  ): Promise<{ user: UserJwt | null }> {
    // Recherche de l'utilisateur par token de récupération
    const userJwtInstance = await this.findByRecuperationToken(token);

    // Changement du mot de passe
    const result = await this.changePassword(userJwtInstance.id, password);

    // Suppression du token de récupération pour éviter sa réutilisation
    await this.userJwtRepository.update(userJwtInstance.id, {
      forgetPasswordToken: null,
    });

    return result;
  }

  /**
   * Change le mot de passe d'un utilisateur par son ID
   * @param userId ID de l'utilisateur
   * @param password Nouveau mot de passe
   * @returns Résultat de l'opération avec l'utilisateur mis à jour
   */
  async changePassword(userId: number, password: string) {
    const result: { user: UserJwt | null } = {
      user: null,
    };

    // Recherche de l'utilisateur
    const userJwt = await this.userJwtRepository.findOne(
      {
        id: userId,
      },
      {
        fields: ['username', 'id', 'password', 'activated'] as Array<
          keyof UserJwt
        >,
      },
    );
    if (!userJwt) {
      throw new NotFoundException();
    }

    // Hachage et sauvegarde du nouveau mot de passe
    userJwt.password = await bcrypt.hash(password, 10);
    userJwt.forgetPasswordToken = null; // Réinitialisation du token de récupération
    await this.userJwtRepository.save(userJwt);
    result.user = userJwt;
    return result;
  }

  /**
   * Sauvegarde un utilisateur JWT
   * @param userJwt Utilisateur à sauvegarder
   * @returns L'utilisateur sauvegardé
   */
  async save(userJwt: UserJwt) {
    return await this.userJwtRepository.save(userJwt);
  }

  /**
   * Supprime doucement (soft delete) un utilisateur JWT
   * @param userJwt Utilisateur à supprimer
   * @returns Résultat de l'opération de suppression
   */
  async softRemove(userJwt: UserJwt) {
    return await this.userJwtRepository.softRemove(userJwt);
  }

  /**
   * Récupère l'utilisateur à partir d'un token JWT d'authentification
   * 
   * Vérifie et décode un token JWT, puis récupère l'utilisateur correspondant
   * depuis la base de données. Utilisé pour valider les tokens dans les headers
   * de requêtes authentifiées.
   * 
   * @param token Token JWT présent dans le header Authorization
   * @returns L'utilisateur JWT associé au token
   * @throws BadRequestException si le token est invalide ou malformé
   * @throws NotFoundException si l'utilisateur associé au token n'existe pas
   */
  async findUserFromAuthToken(token: string): Promise<UserJwt> {
    // Vérification et décodage du token JWT
    const payload = await this.jwtService.verifyAsync(token);
    if (!payload || typeof payload !== 'object') {
      throw new BadRequestException('Token invalide');
    }

    // Typage explicite du payload
    interface JwtPayload {
      id: number;
      username: string;
    }

    const typedPayload = payload as JwtPayload;

    // Recherche de l'utilisateur par son ID depuis le token
    const user = await this.userJwtRepository.findOne({
      id: typedPayload.id,
    });

    if (!user) {
      throw new NotFoundException('Utilisateur non trouvé');
    }

    return user;
  }
}
