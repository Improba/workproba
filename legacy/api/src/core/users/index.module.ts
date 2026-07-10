import { Module, OnModuleInit } from '@nestjs/common';
import { UserRepository } from './repositories/user.repository';
import { BaseModule } from '@lib-improba/base/base.module';
import { AuthJwtModule } from '@lib-improba/modules/auth-jwt/auth-jwt.module';
import { UserService } from './services/user.service';
import { UserRoleEnum } from './entities/user.entity';
import { UserController } from './controllers/user.controller';
import { AdminUserController } from './controllers/admin/admin-user.controller';
import { MikroORM, RequestContext } from '@mikro-orm/core';
import { JwtStrategy } from './jwt.strategy';
import { UserCreatedListener } from './listeners/user-created.listener';

/**
 * Module de gestion des utilisateurs
 *
 * Ce module fournit toutes les fonctionnalités liées à la gestion des utilisateurs :
 * - Authentification JWT via Passport
 * - Gestion des rôles et permissions
 * - CRUD des utilisateurs (endpoints publics et admin)
 * - Création automatique de l'utilisateur admin au démarrage
 * - Écoute des événements de création d'utilisateurs JWT
 *
 * @see UserService pour la logique métier
 * @see UserController pour les endpoints utilisateurs
 * @see AdminUserController pour les endpoints administrateurs
 */
@Module({
  imports: [AuthJwtModule, BaseModule.forCustomRepository([UserRepository])],
  controllers: [UserController, AdminUserController],
  providers: [UserService, JwtStrategy, UserCreatedListener],
  exports: [UserService],
})
export class UsersModule implements OnModuleInit {
  constructor(
    private readonly usersService: UserService,
    private readonly mikroORM: MikroORM,
  ) {}

  /**
   * Initialisation du module au démarrage de l'application
   *
   * Cette méthode est appelée automatiquement par NestJS lors du démarrage.
   * Elle crée automatiquement un utilisateur administrateur si les variables
   * d'environnement ADMINUSER_LOGIN et ADMINUSER_PASSWORD sont définies.
   *
   * Gestion des erreurs :
   * - Si les tables n'existent pas encore (base de données fraîche), met à jour
   *   le schéma puis réessaie la création
   * - Si l'utilisateur admin existe déjà, ignore la création
   *
   * Variables d'environnement requises :
   * - ADMINUSER_LOGIN : Nom d'utilisateur de l'admin
   * - ADMINUSER_PASSWORD : Mot de passe de l'admin
   */
  async onModuleInit() {
    console.info(`Users module initialization...`);

    await RequestContext.create(this.mikroORM.em, async () => {
      // ****************
      // Création automatique de l'utilisateur administrateur
      // ****************

      const username = process.env.ADMINUSER_LOGIN;
      const password = process.env.ADMINUSER_PASSWORD;
      if (username && password) {
        try {
          const role = UserRoleEnum.Admin;
          const users = await this.usersService.findWithUsername(
            <string>username,
          );
          if (users && users.length === 0) {
            console.info('Creating the admin user...');
            await this.usersService.create({
              roles: [role],
              userJwt: {
                username,
                password,
                activated: true,
              },
            });
          } else {
            console.info('The admin user already exists. Skip creation step.');
          }
        } catch (err: any) {
          // Si les tables n'existent pas encore (base de données fraîche),
          // rejete avec une erreur
          const isMissingTable =
            err?.code === '42P01' ||
            /relation ".*" does not exist/i.test(String(err?.message));
          if (isMissingTable) {
            console.warn(
              'Users tables not found. Run migrations first (e.g. npx mikro-orm migration:up). Skipping admin user creation.',
            );
          } else {
            throw err;
          }
        }
      }

      // ****************
    });

    console.info(`Users module initialization done.`);
  }
}

