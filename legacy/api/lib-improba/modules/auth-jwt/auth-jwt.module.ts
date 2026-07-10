import { Module } from '@nestjs/common';
import { PassportModule } from '@nestjs/passport';
import { JwtModule } from '@nestjs/jwt';
import { ConfigModule, ConfigService } from '@nestjs/config';

import { AuthJwtController } from './controllers/auth-jwt.controller';
import { UserJwtService } from './services/user-jwt.service';
import { UserJwtRepository } from './repositories/user-jwt.repository';
import { BaseModule } from '@lib-improba/base/base.module';

/**
 * Module d'authentification JWT
 * 
 * Ce module fournit une authentification basée sur les tokens JWT pour l'application NestJS.
 * Il gère l'enregistrement, la connexion, la déconnexion, l'activation de compte et la réinitialisation de mot de passe.
 * 
 * Configuration requise :
 * - JWT_SECRET : Clé secrète pour signer les tokens JWT (obligatoire)
 * - JWT_EXPIRES_IN : Durée de validité des tokens (optionnel, défaut: '1h')
 * - FRONTEND_URL : URL du frontend pour la redirection après déconnexion (obligatoire)
 * - SENDGRID_API_KEY : Clé API SendGrid pour l'envoi d'emails (optionnel)
 * - EMAIL_FROM : Adresse email expéditrice vérifiée (optionnel)
 * - APP_NAME : Nom de l'application utilisé dans les sujets d'email (optionnel)
 */
@Module({
  imports: [
    BaseModule.forCustomRepository([UserJwtRepository]),
    PassportModule,
    ConfigModule,
    JwtModule.registerAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('JWT_SECRET'),
        // L'expiration du token est gérée dans UserJwtService.login() via JWT_EXPIRES_IN
        // Par défaut : 1 heure ('1h')
      }),
    }),
  ],
  controllers: [AuthJwtController],
  providers: [UserJwtService],
  exports: [UserJwtService],
})
export class AuthJwtModule {}
