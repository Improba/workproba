import {
  Body,
  Controller,
  Get,
  HttpException,
  Post,
  Req,
  Res,
  HttpStatus,
  UnauthorizedException,
  HttpCode,
} from '@nestjs/common';
import { Response } from 'express';
import { ConfigService } from '@nestjs/config';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBody,
  ApiBearerAuth,
} from '@nestjs/swagger';

import { BaseController } from '@lib-improba/base/base.controller';
import { IsNotEmpty, IsOptional, IsBoolean } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

import { UserJwtRepository } from '../repositories/user-jwt.repository';
import { UserJwt } from '../entities/user-jwt.entity';
import {
  UserJwtService,
  SuccessResponse,
  TokenResponse,
} from '../services/user-jwt.service';

/**
 * DTO pour la création d'un utilisateur JWT
 * 
 * Utilisé lors de l'enregistrement d'un nouvel utilisateur via l'endpoint /register.
 * Le mot de passe sera automatiquement hashé avec bcrypt avant la sauvegarde.
 */
export class UserJwtCreateDto {
  /** Nom d'utilisateur unique (peut être un email) */
  @ApiProperty({ description: 'Nom d\'utilisateur unique (peut être un email)', example: 'john.doe@example.com' })
  @IsNotEmpty()
  username!: string;

  /** Mot de passe en clair (sera hashé lors de la création) */
  @ApiProperty({ description: 'Mot de passe en clair (sera hashé lors de la création)', example: 'password123' })
  @IsNotEmpty()
  password!: string;

  /** Statut d'activation du compte (optionnel, défaut: false) */
  @ApiProperty({ required: false, description: 'Statut d\'activation du compte', example: false, default: false })
  @IsOptional()
  @IsBoolean()
  activated?: boolean;
}

/**
 * Contrôleur gérant les endpoints d'authentification JWT
 * 
 * Ce contrôleur expose les routes REST pour l'authentification :
 * - POST /auth-jwt/login : Connexion d'un utilisateur
 * - POST /auth-jwt/refreshToken : Rafraîchissement d'un token JWT
 * - GET /auth-jwt/logout : Déconnexion et redirection vers le frontend
 * - POST /auth-jwt/register : Enregistrement d'un nouvel utilisateur (DÉSACTIVÉ PAR DÉFAUT)
 * - POST /auth-jwt/forgot-password : Demande de réinitialisation de mot de passe
 * - POST /auth-jwt/reset-password : Réinitialisation du mot de passe avec un token
 */
@ApiTags('auth')
@Controller('auth-jwt')
export class AuthJwtController extends BaseController {
  /**
   * Détermine si l'enregistrement de nouveaux utilisateurs est autorisé via cette API
   * 
   * Par défaut à `false` pour désactiver l'enregistrement public.
   * Modifier cette valeur à `true` pour activer l'enregistrement public.
   * Quand désactivé, l'endpoint /register retourne une erreur 401.
   */
  private allowRegisterNewUserFromAuthJwt = false;

  constructor(
    private readonly userJwtRepository: UserJwtRepository,
    private readonly userJwtService: UserJwtService,
    private readonly configService: ConfigService,
  ) {
    super();
  }

  /**
   * Endpoint de connexion
   * 
   * Authentifie un utilisateur avec son nom d'utilisateur et son mot de passe.
   * Retourne un token JWT valide si les identifiants sont corrects.
   * 
   * @param username Nom d'utilisateur ou email de l'utilisateur
   * @param password Mot de passe en clair
   * @returns Objet contenant le token JWT : `{ token: string }`
   * @throws HttpException (403) si les identifiants sont incorrects
   */
  @Post('login')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Connexion d\'un utilisateur', description: 'Authentifie un utilisateur et retourne un token JWT' })
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        username: { type: 'string', example: 'admin' },
        password: { type: 'string', example: 'password123' },
      },
      required: ['username', 'password'],
    },
  })
  @ApiResponse({ status: 200, description: 'Connexion réussie', schema: { type: 'object', properties: { token: { type: 'string' } } } })
  @ApiResponse({ status: 403, description: 'Identifiants incorrects' })
  async postLogin(
    @Body('username') username: string,
    @Body('password') password: string,
  ): Promise<{ token: string }> {
    // Vérification des identifiants (lance une exception si incorrects)
    const userJwt = await this.userJwtService.findByUsernamePassword(
      username,
      password,
    );

    // Génération du token JWT avec expiration configurée
    const jwt = this.userJwtService.login(userJwt);
    return {
      token: jwt,
    };
  }

  /**
   * Endpoint de rafraîchissement de token
   * 
   * Génère un nouveau token JWT à partir d'un token existant valide.
   * Le nouveau token aura une nouvelle date d'expiration.
   * 
   * @param token Token JWT existant à rafraîchir
   * @returns Objet contenant le nouveau token JWT : `{ token: string }`
   * @throws UnauthorizedException si le token fourni est invalide ou expiré
   */
  @Post('refreshToken')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Rafraîchir un token JWT', description: 'Génère un nouveau token JWT à partir d\'un token existant' })
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        token: { type: 'string', example: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' },
      },
      required: ['token'],
    },
  })
  @ApiResponse({ status: 200, description: 'Token rafraîchi avec succès', schema: { type: 'object', properties: { token: { type: 'string' } } } })
  @ApiResponse({ status: 401, description: 'Token invalide ou expiré' })
  async refreshToken(@Body('token') token: string): Promise<{ token: string }> {
    const jwt = this.userJwtService.createNewTokenFromPreviousOne(token);
    
    if (!jwt) {
      throw new UnauthorizedException('Token cannot be refreshed');
    }
    
    return {
      token: jwt,
    };
  }

  /**
   * Endpoint de déconnexion
   * 
   * Termine la session de l'utilisateur et redirige vers l'URL du frontend.
   * Note: Cette méthode utilise Passport pour la déconnexion de session.
   * 
   * @param request Objet de requête Express
   * @param response Objet de réponse Express pour la redirection
   */
  @Get('logout')
  @ApiOperation({ summary: 'Déconnexion', description: 'Termine la session et redirige vers le frontend' })
  @ApiResponse({ status: 302, description: 'Redirection vers le frontend' })
  logout(@Req() request: Express.Request, @Res() response: Response): void {
    // Déconnexion via Passport si une session existe
    if (request.logout) {
      request.logout(() => {});
    }
    
    // Redirection vers le frontend
    const frontendUrl = this.configService.get<string>('FRONTEND_URL');
    response.redirect(frontendUrl || '/');
  }

  /**
   * Endpoint d'enregistrement
   * 
   * Crée un nouvel utilisateur JWT dans le système.
   * L'enregistrement peut être désactivé en modifiant `allowRegisterNewUserFromAuthJwt`.
   * 
   * ⚠️ DÉSACTIVÉ PAR DÉFAUT : L'inscription publique est désactivée par défaut.
   * 
   * POUR RÉACTIVER L'INSCRIPTION :
   * 1. Décommenter tout le bloc ci-dessous (de @Post('register') jusqu'à la fin de la méthode)
   * 2. Modifier `allowRegisterNewUserFromAuthJwt = true` (ligne ~78)
   * 3. Dans le frontend :
   *    - Login.vue : Retirer `:disable="true"` et le style `opacity: 0.5` du bouton "S'inscrire"
   *    - Register.vue : Retirer `:disable="true"` et les styles d'opacité des champs du formulaire
   *    - Register.vue : Retirer la bannière d'avertissement et réactiver le bouton "S'inscrire"
   * 
   * @param userJwtCreateDto Données de création de l'utilisateur (username, password, activated optionnel)
   * @returns Informations de l'utilisateur créé (id et username uniquement)
   * @throws HttpException (401) si l'enregistrement n'est pas autorisé
   * @throws HttpException (400) si la création échoue (ex: username déjà utilisé)
   */
  // ============================================
  // ENDPOINT D'INSCRIPTION - DÉSACTIVÉ PAR DÉFAUT
  // ============================================
  // Pour réactiver cet endpoint :
  // 1. Décommenter toutes les lignes ci-dessous (supprimer les // au début de chaque ligne)
  // 2. Modifier la propriété allowRegisterNewUserFromAuthJwt = true (ligne ~78)
  // 3. Modifier le frontend :
  //    - front/src/pages/auth/Login.vue : Retirer :disable="true" et style="opacity: 0.5; cursor: not-allowed;" du bouton register
  //    - front/src/pages/auth/Register.vue : 
  //      * Retirer la bannière d'avertissement (q-banner avec bg-warning)
  //      * Retirer :disable="true" et style="opacity: 0.5;" de tous les q-input
  //      * Retirer :disable="true" et style="opacity: 0.5; cursor: not-allowed;" du bouton register
  // ============================================
  // @Post('register')
  // @ApiOperation({ summary: 'Enregistrement d\'un nouvel utilisateur', description: 'Crée un nouveau compte utilisateur (DÉSACTIVÉ PAR DÉFAUT)' })
  // @ApiBody({ type: UserJwtCreateDto })
  // @ApiResponse({ status: 201, description: 'Utilisateur créé avec succès', schema: { type: 'object', properties: { id: { type: 'number' }, username: { type: 'string' } } } })
  // @ApiResponse({ status: 400, description: 'Échec de la création (ex: username déjà utilisé)' })
  // @ApiResponse({ status: 401, description: 'Enregistrement non autorisé' })
  // async postRegister(
  //   @Body() userJwtCreateDto: UserJwtCreateDto,
  // ): Promise<Pick<UserJwt, 'id' | 'username'>> {
  //   if (!this.allowRegisterNewUserFromAuthJwt) {
  //     throw new HttpException(
  //       'Création non autorisée',
  //       HttpStatus.UNAUTHORIZED,
  //     );
  //   }
  //
  //   try {
  //     const result = await this.userJwtService.create(userJwtCreateDto);
  //     return result;
  //   } catch (err) {
  //     throw new HttpException(
  //       'Création impossible',
  //       HttpStatus.BAD_REQUEST,
  //     );
  //   }
  // }

  /**
   * Endpoint d'activation de compte (désactivé par défaut)
   * 
   * Active un compte utilisateur via un token d'activation.
   * Cet endpoint est commenté par défaut. Pour l'activer, décommenter le code ci-dessous.
   * 
   * @param token Token d'activation généré lors de la création du compte
   * @returns Résultat de l'opération d'activation
   * @throws HttpException (400) si l'activation échoue
   */
  // @Post('activate')
  // async postActivate(@Body('token') token: string): Promise<SuccessResponse> {
  //   const response = new SuccessResponse();
  //   const result = await this.userJwtService.activate(token);
  //
  //   if (result && result.success) {
  //     response.success = true;
  //     response.message = result.message || 'Utilisateur activé';
  //     response.errors = [];
  //   } else {
  //     throw new HttpException('Activation impossible', HttpStatus.BAD_REQUEST);
  //   }
  //
  //   return response;
  // }

  /**
   * Endpoint de demande de réinitialisation de mot de passe
   * 
   * Envoie un email contenant un lien pour réinitialiser le mot de passe.
   * Un token de réinitialisation est généré et envoyé par email via SendGrid.
   * 
   * Limitation : Un email ne peut être envoyé que toutes les 10 minutes par utilisateur.
   * 
   * @param username Nom d'utilisateur ou email de l'utilisateur
   * @returns Résultat de l'opération avec statut de succès
   * @throws HttpException (400) si l'utilisateur n'existe pas ou si un email a déjà été envoyé récemment
   */
  @Post('forgot-password')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Demande de réinitialisation de mot de passe', description: 'Envoie un email avec un lien de réinitialisation' })
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        username: { type: 'string', example: 'admin' },
      },
      required: ['username'],
    },
  })
  @ApiResponse({ status: 200, description: 'Email de réinitialisation envoyé' })
  @ApiResponse({ status: 400, description: 'Échec de l\'envoi de l\'email' })
  async getNewPassword(
    @Body('username') username: string,
  ): Promise<SuccessResponse> {
    const result = await this.userJwtService.sendMailForNewPassword(username);

    if (!result) {
      throw new HttpException(
        'Récupération impossible',
        HttpStatus.BAD_REQUEST,
      );
    }

    const response = new SuccessResponse();
    response.success = true;
    response.message = 'Mail de récupération de mot de passe envoyé';
    response.errors = [];

    return response;
  }

  /**
   * Endpoint de réinitialisation de mot de passe
   * 
   * Réinitialise le mot de passe d'un utilisateur via un token de récupération valide.
   * Après la réinitialisation, un nouveau token JWT est généré pour connecter automatiquement l'utilisateur.
   * 
   * @param token Token de récupération reçu par email
   * @param password Nouveau mot de passe en clair
   * @returns Token JWT pour une connexion immédiate : `{ token: string }`
   * @throws HttpException (400) si le token est invalide ou si la réinitialisation échoue
   */
  @Post('reset-password')
  @HttpCode(HttpStatus.OK)
  @ApiOperation({ summary: 'Réinitialisation du mot de passe', description: 'Réinitialise le mot de passe avec un token et retourne un JWT' })
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        token: { type: 'string', example: 'reset-token-123' },
        password: { type: 'string', example: 'newPassword123' },
      },
      required: ['token', 'password'],
    },
  })
  @ApiResponse({ status: 200, description: 'Mot de passe réinitialisé avec succès', schema: { type: 'object', properties: { token: { type: 'string' } } } })
  @ApiResponse({ status: 400, description: 'Échec de la réinitialisation' })
  async postNewPassword(
    @Body('token') token: string,
    @Body('password') password: string,
  ): Promise<TokenResponse> {
    const result = await this.userJwtService.changePasswordUser(
      token,
      password,
    );

    if (!result.user) {
      throw new HttpException(
        'Impossible de changer le mot de passe',
        HttpStatus.BAD_REQUEST,
      );
    }

    // Génère un token JWT pour connecter automatiquement l'utilisateur
    const response = new TokenResponse();
    response.token = this.userJwtService.login(result.user);
    response.message = 'Mot de passe réinitialisé avec succès';
    response.errors = [];

    return response;
  }
}
