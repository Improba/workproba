# Module Auth JWT

## Vue d'ensemble

Le module Auth JWT fournit une authentification basée sur les tokens JWT pour les applications NestJS. Il gère :

- L'enregistrement d'utilisateurs (optionnel)
- La connexion et la génération de tokens
- Le rafraîchissement de tokens
- La déconnexion et la fin de session
- L'activation de compte
- La réinitialisation de mot de passe (demande et réinitialisation)
- La recherche et la gestion d'utilisateurs

Construit sur NestJS et MikroORM, il stocke les identifiants des utilisateurs dans une entité `UserJwt` et émet des événements lors des opérations du cycle de vie.

## Installation

```typescript
import { Module } from '@nestjs/common';
import { AuthJwtModule } from '@lib-improba/modules/auth-jwt/auth-jwt.module';

@Module({
  imports: [AuthJwtModule],
})
export class AppModule {}
```

## Configuration

Configurez les variables d'environnement suivantes :

### Variables obligatoires

- **`JWT_SECRET`** : Clé secrète pour signer les tokens JWT (obligatoire)
- **`FRONTEND_URL`** : URL du frontend pour la redirection après déconnexion (obligatoire)

### Variables optionnelles

- **`JWT_EXPIRES_IN`** : Durée de validité des tokens JWT (optionnel, défaut: `'1h'`)
  - Format : `'1h'`, `'30m'`, `'3600s'`, etc.
- **`SENDGRID_API_KEY`** : Clé API SendGrid pour l'envoi d'emails de réinitialisation (optionnel)
- **`EMAIL_FROM`** : Adresse email expéditrice vérifiée dans SendGrid (optionnel)
- **`APP_NAME`** : Nom de l'application utilisé dans les sujets d'email (optionnel, défaut: `'Application'`)

### Exemple de configuration

```bash
JWT_SECRET=votre_cle_secrete_tres_longue_et_aleatoire
FRONTEND_URL=http://localhost:8080
JWT_EXPIRES_IN=1h
SENDGRID_API_KEY=SG.xxxxxxxxxxxxx
EMAIL_FROM=noreply@example.com
APP_NAME=Mon Application
```

## Entités

### `UserJwt`

Entité principale représentant un utilisateur avec authentification JWT.

| Propriété              | Type              | Description                                                      |
| ---------------------- | ----------------- | ---------------------------------------------------------------- |
| `id`                   | `number`          | Clé primaire (héritée de `BaseEntity`)                          |
| `username`             | `string`          | Identifiant de connexion unique (peut être un email)            |
| `password`             | `string`          | Mot de passe hashé avec bcrypt (masqué dans les sérialisations) |
| `activated`            | `boolean`         | Statut d'activation du compte (défaut: `false`)                 |
| `activationToken`      | `string \| null`  | Token unique pour l'activation du compte (masqué)               |
| `lastResetPasswordAt`  | `Date \| null`    | Date de la dernière demande de réinitialisation                 |
| `forgetPasswordToken`  | `string \| null`  | Token unique pour la réinitialisation de mot de passe (masqué)  |

**Propriétés héritées de `BaseEntity`** :
- `createdAt` : Date de création
- `updatedAt` : Date de dernière modification
- `deletedAt` : Date de suppression (soft delete)

### `UserJwtCreateDto`

DTO pour la création d'un utilisateur.

```typescript
export class UserJwtCreateDto {
  username: string;      // Obligatoire
  password: string;       // Obligatoire
  activated?: boolean;    // Optionnel (défaut: false)
}
```

## Services

### `UserJwtService`

Service principal fournissant les opérations d'authentification.

#### Méthodes principales

##### Création et gestion d'utilisateurs

- **`create(dto: UserJwtCreateDto, emitUserCreateSignal = true)`**
  - Crée un nouvel utilisateur avec mot de passe hashé
  - Génère un token d'activation unique (UUID v4)
  - Émet l'événement `authJwt.userCreated` si `emitUserCreateSignal` est `true`
  - Retourne : `{ id: number, username: string }`

- **`save(user: UserJwt)`**
  - Sauvegarde les modifications d'un utilisateur

- **`softRemove(user: UserJwt)`**
  - Supprime doucement un utilisateur (soft delete)

##### Authentification

- **`login(user: UserJwt)`**
  - Génère un token JWT signé pour l'utilisateur
  - Durée de validité configurée via `JWT_EXPIRES_IN` (défaut: `'1h'`)
  - Retourne : `string` (token JWT)

- **`createNewTokenFromPreviousOne(token: string)`**
  - Rafraîchit un token JWT existant valide
  - Génère un nouveau token avec la même expiration configurée
  - Retourne : `string | null` (nouveau token ou null si invalide)

- **`findByUsernamePassword(username: string, password: string)`**
  - Authentifie un utilisateur par username et mot de passe
  - Vérifie le mot de passe avec bcrypt
  - Retourne : `UserJwt` (utilisateur complet)
  - Lance : `BadRequestException` si les identifiants sont incorrects

- **`findUserFromAuthToken(token: string)`**
  - Récupère l'utilisateur à partir d'un token JWT d'authentification
  - Vérifie et décode le token, puis récupère l'utilisateur
  - Retourne : `UserJwt`
  - Lance : `BadRequestException` si le token est invalide

##### Recherche d'utilisateurs

- **`findByUsername(username: string)`**
  - Recherche un utilisateur actif par username (insensible à la casse)
  - Retourne : `UserJwt | null`

- **`findById(id: number)`**
  - Récupère un utilisateur par son ID
  - Retourne : `UserJwt`
  - Lance : `NotFoundException` si non trouvé

- **`findByRecuperationToken(token: string)`**
  - Recherche un utilisateur par son token de réinitialisation
  - Retourne : `UserJwt`
  - Lance : `NotFoundException` si non trouvé

##### Activation de compte

- **`activate(activationToken: string)`**
  - Active un compte utilisateur avec le token d'activation
  - Si déjà activé, retourne un succès sans modification
  - Émet l'événement `authJwt.userActivated` après activation
  - Retourne : `SuccessResponse`

##### Réinitialisation de mot de passe

- **`sendMailForNewPassword(email: string)`**
  - Génère un token de réinitialisation unique (UUID v4)
  - Limite : 1 email toutes les 10 minutes par utilisateur
  - Émet l'événement `authJwt.passwordForgot`
  - Envoie un email via SendGrid si configuré
  - Retourne : `UserJwt`
  - Lance : `NotFoundException` si l'utilisateur n'existe pas
  - Lance : `BadRequestException` si un email a déjà été envoyé récemment

- **`changePasswordUser(token: string, password: string)`**
  - Change le mot de passe via un token de réinitialisation
  - Supprime le token après utilisation
  - Retourne : `{ user: UserJwt | null }`

- **`changePassword(userId: number, password: string)`**
  - Change le mot de passe d'un utilisateur par son ID
  - Hash le nouveau mot de passe avec bcrypt
  - Retourne : `{ user: UserJwt | null }`

#### Classes de réponse

##### `TokenResponse`

```typescript
export class TokenResponse {
  token: string;        // Token JWT
  message: string;      // Message de réponse
  errors: string[];     // Liste des erreurs (vide si succès)
}
```

##### `SuccessResponse`

```typescript
export class SuccessResponse {
  success: boolean;      // Statut de succès
  message: string;      // Message de réponse
  errors: string[];     // Liste des erreurs (vide si succès)
  output?: any;        // Résultat spécifique optionnel
}
```

## Contrôleurs

### `AuthJwtController` (chemin de base : `/auth-jwt`)

Contrôleur REST exposant les endpoints d'authentification.

| Endpoint              | Méthode | Body                                          | Description                                                      |
| --------------------- | ------- | --------------------------------------------- | ---------------------------------------------------------------- |
| `/login`              | POST    | `{ username: string; password: string }`     | Authentifie un utilisateur et retourne `{ token: string }`      |
| `/refreshToken`       | POST    | `{ token: string }`                           | Rafraîchit un token JWT et retourne `{ token: string }`          |
| `/logout`             | GET     | —                                             | Termine la session et redirige vers `FRONTEND_URL`               |
| `/register`           | POST    | `UserJwtCreateDto`                             | Crée un nouvel utilisateur (si activé)                          |
| `/forgot-password`    | POST    | `{ username: string }`                        | Envoie un email de réinitialisation de mot de passe              |
| `/reset-password`     | POST    | `{ token: string; password: string }`         | Réinitialise le mot de passe et retourne `{ token: string }`     |

#### Notes importantes

- **Enregistrement** : L'endpoint `/register` peut être désactivé en modifiant `allowRegisterNewUserFromAuthJwt` dans le contrôleur (défaut: `true`)
- **Activation** : L'endpoint `/activate` est commenté par défaut. Pour l'activer, décommenter le code dans le contrôleur

## Repositories

### `UserJwtRepository`

Repository étendant `BaseRepository<UserJwt>` pour les opérations de base de données.

**Méthodes héritées** :
- `findOne()`, `findOneById()`, `findAndPaginate()`
- `save()`, `update()`, `softDelete()`, `hardDelete()`

**Enregistrement** :
- Enregistré via `BaseModule.forCustomRepository([UserJwtRepository])`
- Injection : `@InjectRepository(UserJwtRepository)`

## Événements

Les événements sont émis via `EventEmitter2` et peuvent être écoutés avec `@OnEvent()`.

### Événements disponibles

| Événement                  | Classe d'événement              | Émis lors de                                    |
| -------------------------- | ------------------------------- | ----------------------------------------------- |
| `authJwt.userCreated`      | `AuthJwtUserCreatedEvent`       | Création d'un nouvel utilisateur                |
| `authJwt.userActivated`    | `AuthJwtUserActivatedEvent`     | Activation d'un compte utilisateur              |
| `authJwt.passwordForgot`   | `AuthJwtPasswordForgotEvent`    | Demande de réinitialisation de mot de passe     |
| `authJwt.userDeleted`       | `AuthJwtUserDeletedEvent`       | Suppression d'un utilisateur (non émis par défaut) |

### Exemple d'écoute d'événement

```typescript
import { Injectable } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { AuthJwtUserCreatedEvent } from '@lib-improba/modules/auth-jwt/events/auth-jwt-user-created.event';

@Injectable()
export class UserListenerService {
  @OnEvent('authJwt.userCreated')
  handleUserCreated(event: AuthJwtUserCreatedEvent) {
    console.log('Nouvel utilisateur créé:', event.user.username);
    // Traitement personnalisé (ex: envoyer un email de bienvenue)
  }
}
```

## Utilisation

### Protection de routes avec JWT

Pour protéger des routes avec l'authentification JWT, vous devez d'abord configurer une stratégie JWT Passport.

**Exemple de stratégie JWT** :

```typescript
import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy, 'jwt-user') {
  constructor(private userJwtService: UserJwtService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      secretOrKey: process.env.JWT_SECRET,
    });
  }

  async validate(payload: { id: number; username: string }) {
    return await this.userJwtService.findById(payload.id);
  }
}
```

**Protection d'une route** :

```typescript
import { Controller, Get, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Controller('protected')
export class ProtectedController {
  @Get('profile')
  @UseGuards(AuthGuard('jwt-user'))
  getProfile(@Request() req) {
    // req.user contient l'utilisateur JWT authentifié
    return req.user;
  }
}
```

### Injection du service

```typescript
import { Injectable } from '@nestjs/common';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';

@Injectable()
export class MyService {
  constructor(private readonly userJwtService: UserJwtService) {}

  async doSomething() {
    const user = await this.userJwtService.findByUsername('john@example.com');
    // ...
  }
}
```

## Sécurité

### Bonnes pratiques

1. **JWT_SECRET** : Utilisez une clé secrète longue et aléatoire (minimum 32 caractères)
2. **Expiration des tokens** : Configurez une expiration raisonnable (`JWT_EXPIRES_IN`)
3. **HTTPS** : Utilisez toujours HTTPS en production pour protéger les tokens
4. **Validation** : Validez toujours les tokens côté serveur avant de faire confiance aux données
5. **Mot de passe** : Les mots de passe sont automatiquement hashés avec bcrypt (10 rounds)
6. **Rate limiting** : La réinitialisation de mot de passe est limitée à 1 demande toutes les 10 minutes

### Tokens

- Les tokens sont signés avec `JWT_SECRET` via l'algorithme HS256
- L'expiration est configurable via `JWT_EXPIRES_IN` (défaut: `'1h'`)
- Les tokens de réinitialisation sont des UUID v4 uniques et sécurisés

## Structure du module

```
auth-jwt/
├── auth-jwt.module.ts          # Module principal
├── controllers/
│   └── auth-jwt.controller.ts   # Contrôleur REST
├── services/
│   └── user-jwt.service.ts      # Service principal
├── entities/
│   └── user-jwt.entity.ts       # Entité UserJwt et DTO
├── repositories/
│   └── user-jwt.repository.ts   # Repository
├── events/                      # Événements émis
│   ├── auth-jwt-user-created.event.ts
│   ├── auth-jwt-user-activated.event.ts
│   ├── auth-jwt-password-forgot.event.ts
│   └── auth-jwt-user-deleted.event.ts
└── README.md                    # Cette documentation
```

## Support

Pour toute question ou problème, consultez la documentation du projet ou contactez l'équipe de développement.
