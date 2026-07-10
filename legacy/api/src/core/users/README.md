# Module Users

Module de gestion des utilisateurs de l'application. Ce module fournit toutes les fonctionnalités liées à la gestion des utilisateurs, l'authentification JWT, les rôles et permissions.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Architecture](#architecture)
- [Endpoints](#endpoints)
- [Authentification](#authentification)
- [Rôles et permissions](#rôles-et-permissions)
- [Entités](#entités)
- [Services](#services)
- [Configuration](#configuration)

## 🎯 Vue d'ensemble

Le module Users gère :
- ✅ Authentification JWT via Passport
- ✅ Gestion des rôles (Admin, User)
- ✅ CRUD des utilisateurs
- ✅ Endpoints publics (utilisateur connecté)
- ✅ Endpoints administrateurs
- ✅ Création automatique de l'utilisateur admin au démarrage
- ✅ Écoute des événements de création d'utilisateurs JWT

## 🏗️ Architecture

```
users/
├── controllers/
│   ├── user.controller.ts          # Endpoints utilisateurs (GET /users/current, PATCH /users/current)
│   └── admin/
│       └── admin-user.controller.ts # Endpoints administrateurs (CRUD complet)
├── services/
│   └── user.service.ts             # Logique métier des utilisateurs
├── repositories/
│   └── user.repository.ts          # Accès aux données (MikroORM)
├── entities/
│   └── user.entity.ts              # Entité User
├── guards/
│   ├── jwt-auth.guard.ts           # Guard d'authentification JWT
│   └── user-roles.guard.ts         # Guard de vérification des rôles
├── decorators/
│   └── roles.ts                    # Décorateur @Roles()
├── jwt.strategy.ts                 # Stratégie Passport JWT
├── listeners/
│   └── user-created.listener.ts    # Listener pour les événements auth-jwt
└── index.module.ts                 # Module NestJS principal
```

## 🔌 Endpoints

### Endpoints utilisateurs (authentifiés)

#### `GET /users/current`
Récupère les informations de l'utilisateur actuellement connecté.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `User` ou `Admin`

**Réponse** :
```json
{
  "id": 1,
  "firstname": "John",
  "lastname": "Doe",
  "fullname": "John Doe",
  "roles": ["user"],
  "preferDarkTheme": true,
  "resetPasswordOngoing": false,
  "isAdmin": false,
  "userJwt": {
    "id": 1,
    "username": "john.doe@example.com",
    "activated": true
  },
  "createdAt": "2024-01-01T00:00:00.000Z",
  "updatedAt": "2024-01-01T00:00:00.000Z"
}
```

#### `PATCH /users/current`
Met à jour les informations de l'utilisateur actuellement connecté.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `User` ou `Admin`

**Body** :
```json
{
  "firstname": "Jane",
  "lastname": "Smith",
  "preferDarkTheme": false,
  "resetPasswordOngoing": false
}
```

### Endpoints administrateurs

#### `GET /users-admin`
Liste tous les utilisateurs.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

#### `GET /users-admin/paginate`
Récupère une liste paginée d'utilisateurs avec filtres et tri.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

**Query Parameters** :
- `limit` : Nombre d'éléments par page (défaut: 10)
- `offset` : Décalage pour la pagination (défaut: 0)
- `orderBy` : Champ de tri (`id`, `firstname`, `lastname`, `username`)
- `order` : Ordre de tri (`ASC` ou `DESC`)
- `q` : Recherche textuelle (nom, prénom, username)
- `role` : Filtrer par rôle (`admin` ou `user`)

**Exemple** :
```
GET /users-admin/paginate?limit=10&offset=0&orderBy=firstname&order=ASC&q=John&role=user
```

#### `GET /users-admin/:id`
Récupère un utilisateur par son ID.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

#### `POST /users-admin`
Crée un nouvel utilisateur.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

**Body** :
```json
{
  "firstname": "John",
  "lastname": "Doe",
  "roles": ["user"],
  "userJwt": {
    "username": "john.doe@example.com",
    "password": "securePassword123",
    "activated": true
  }
}
```

#### `PATCH /users-admin`
Met à jour un utilisateur existant.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

**Body** :
```json
{
  "id": 1,
  "firstname": "Jane",
  "lastname": "Smith",
  "roles": ["admin"],
  "preferDarkTheme": false
}
```

#### `PATCH /users-admin/current`
Met à jour l'administrateur actuellement connecté.

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

#### `DELETE /users-admin/:id`
Supprime un utilisateur (soft delete).

**Authentification** : Requise (JWT Bearer Token)  
**Rôles** : `Admin`

**Note** : Le paramètre `id` correspond à l'ID du UserJwt, pas de l'utilisateur.

## 🔐 Authentification

Le module utilise Passport avec la stratégie JWT pour l'authentification.

### Configuration

La stratégie JWT est configurée dans `jwt.strategy.ts` :
- Extraction du token depuis le header `Authorization: Bearer <token>`
- Validation avec `JWT_SECRET`
- Récupération de l'utilisateur depuis le payload JWT

### Utilisation dans les contrôleurs

```typescript
import { UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '@users/guards/jwt-auth.guard';
import { UserRolesGuard } from '@users/guards/user-roles.guard';
import { Roles } from '@users/decorators/roles';
import { UserRoleEnum } from '@users/entities/user.entity';

@Controller('my-route')
export class MyController {
  @Get('protected')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.User)
  async protectedRoute(@Req() req: any) {
    // req.user contient l'utilisateur authentifié
    return req.user;
  }
}
```

## 👥 Rôles et permissions

Le module définit deux rôles principaux :

- **`User`** : Utilisateur standard
- **`Admin`** : Administrateur avec tous les droits

### Système de permissions

Le `UserRolesGuard` vérifie les permissions selon ces règles :

1. **Route publique** : Si aucun `@Roles()` n'est spécifié, la route est accessible à tous les utilisateurs authentifiés
2. **Administrateurs** : Les administrateurs ont accès à toutes les routes protégées
3. **Rôles multiples** : Un utilisateur doit avoir au moins un des rôles autorisés

### Exemples

```typescript
// Route accessible uniquement aux administrateurs
@Get('admin-only')
@UseGuards(JwtAuthGuard, UserRolesGuard)
@Roles(UserRoleEnum.Admin)
async adminOnly() { ... }

// Route accessible aux utilisateurs et administrateurs
@Get('user-or-admin')
@UseGuards(JwtAuthGuard, UserRolesGuard)
@Roles(UserRoleEnum.User, UserRoleEnum.Admin)
async userOrAdmin() { ... }

// Route publique (authentifiée mais sans restriction de rôle)
@Get('public')
@UseGuards(JwtAuthGuard, UserRolesGuard)
async public() { ... }
```

## 📦 Entités

### User

Entité principale représentant un utilisateur de l'application.

**Propriétés** :
- `id` : Identifiant unique (bigint)
- `firstname` : Prénom (nullable)
- `lastname` : Nom (nullable)
- `fullname` : Nom complet (calculé automatiquement)
- `roles` : Liste des rôles (`UserRoleEnum[]`)
- `preferDarkTheme` : Préférence pour le thème sombre (défaut: `true`)
- `resetPasswordOngoing` : Indique si une réinitialisation de mot de passe est en cours
- `isAdmin` : Indique si l'utilisateur est administrateur (calculé automatiquement)
- `userJwt` : Relation OneToOne avec `UserJwt` (informations d'authentification)
- `createdAt` : Date de création
- `updatedAt` : Date de dernière modification
- `deletedAt` : Date de suppression (soft delete)

**Hérite de** : `BaseEntity`

## 🔧 Services

### UserService

Service principal pour la gestion des utilisateurs.

**Méthodes principales** :

- `findFromUserJwtId(id: number)` : Trouve un utilisateur par l'ID de son UserJwt
- `getAll()` : Récupère tous les utilisateurs
- `findOneById(id: number)` : Trouve un utilisateur par son ID
- `findWithUsername(username: string)` : Trouve des utilisateurs par nom d'utilisateur
- `findCurrentUser(username: string)` : Trouve l'utilisateur actuel par username
- `findCurrentUserById(id: number)` : Trouve l'utilisateur actuel par ID UserJwt
- `create(options: UserCreateForAdminDto)` : Crée un nouvel utilisateur (admin)
- `createFromAuthJwt(event: AuthJwtUserCreatedEvent)` : Crée un utilisateur depuis un événement
- `update(dto: UserUpdateDto)` : Met à jour un utilisateur (standard)
- `updateAdmin(dto: AdminUserUpdateDto)` : Met à jour un utilisateur (admin)
- `delete(id: number)` : Supprime un utilisateur (soft delete)
- `paginate(dto: PaginateUserDTO)` : Pagine les utilisateurs avec filtres

## ⚙️ Configuration

### Variables d'environnement

Le module nécessite les variables suivantes :

- `JWT_SECRET` : Clé secrète pour signer les tokens JWT (obligatoire)
- `ADMINUSER_LOGIN` : Nom d'utilisateur de l'admin à créer au démarrage (optionnel)
- `ADMINUSER_PASSWORD` : Mot de passe de l'admin à créer au démarrage (optionnel)

### Initialisation automatique

Au démarrage de l'application, si `ADMINUSER_LOGIN` et `ADMINUSER_PASSWORD` sont définis :
1. Le module vérifie si un utilisateur avec ce nom d'utilisateur existe
2. Si aucun utilisateur n'existe, il crée automatiquement un utilisateur admin
3. Si les tables n'existent pas encore, le schéma est mis à jour puis l'utilisateur est créé

## 🔄 Événements

Le module écoute l'événement `authJwt.userCreated` émis par le module `auth-jwt` :

- Lorsqu'un `UserJwt` est créé via le module auth-jwt
- Le listener `UserCreatedListener` crée automatiquement un `User` associé
- L'utilisateur créé a les valeurs par défaut : rôle `User`, thème sombre activé

## 📚 Exemples d'utilisation

### Créer un utilisateur (admin)

```typescript
const newUser = await userService.create({
  firstname: 'John',
  lastname: 'Doe',
  roles: [UserRoleEnum.User],
  userJwt: {
    username: 'john.doe@example.com',
    password: 'securePassword123',
    activated: true,
  },
});
```

### Paginer les utilisateurs

```typescript
const result = await userService.paginate({
  limit: 10,
  offset: 0,
  orderBy: 'firstname',
  order: QueryOrder.ASC,
  q: 'John',
  role: UserRoleEnum.User,
});

// result.results contient les utilisateurs
// result.count contient le nombre total
```

### Vérifier les permissions dans un guard personnalisé

```typescript
@Injectable()
export class MyCustomGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const roles = this.reflector.get<string[]>('roles', context.getHandler());
    const user = context.switchToHttp().getRequest().user;
    
    if (!roles) return true;
    if (user.roles.includes(UserRoleEnum.Admin)) return true;
    return roles.some(role => user.roles.includes(role));
  }
}
```

## 🔗 Dépendances

- `@lib-improba/base` : BaseService, BaseRepository, BaseEntity
- `@lib-improba/modules/auth-jwt` : Module d'authentification JWT
- `@nestjs/passport` : Authentification Passport
- `@nestjs/jwt` : Gestion des tokens JWT
- `@mikro-orm/core` : ORM pour l'accès aux données

## 📝 Notes

- Les utilisateurs sont supprimés en soft delete (le champ `deletedAt` est défini)
- Lors de la suppression, le username du UserJwt est renommé pour éviter les conflits
- Le champ `isAdmin` est calculé automatiquement depuis les rôles
- Le champ `fullname` est généré automatiquement depuis `firstname` et `lastname`

