import { Expose } from 'class-transformer';
import { Cascade, wrap } from '@mikro-orm/core';
import {
  Entity,
  OneToOne,
  Property,
  OnLoad,
  BeforeCreate,
  BeforeUpdate,
  Enum,
  Index,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { UserJwt } from '@lib-improba/modules/auth-jwt/entities/user-jwt.entity';

// Import conditionnel de ApiProperty pour éviter les erreurs lors des migrations CLI
let ApiProperty: any;
try {
  ApiProperty = require('@nestjs/swagger').ApiProperty;
} catch (e) {
  // Si @nestjs/swagger n'est pas disponible (ex: migrations CLI), utiliser un décorateur vide
  ApiProperty = () => () => {};
}

export enum UserRoleEnum {
  Admin = 'admin',
  User = 'user',
}

@Entity() 
export class User extends BaseEntity {
  @ApiProperty({ description: 'Prénom de l\'utilisateur', example: 'John', nullable: true, required: false })
  @Property({ type: 'string', length: 200, nullable: true })
  firstname!: string | null;

  @ApiProperty({ description: 'Nom de l\'utilisateur', example: 'Doe', nullable: true, required: false })
  @Property({ type: 'string', length: 200, nullable: true })
  lastname!: string | null;

  @ApiProperty({ description: 'Nom complet de l\'utilisateur (calculé automatiquement)', example: 'John Doe', nullable: true, required: false })
  @Property({ persist: false })
  @Expose()
  fullname?: string | null;

  @OnLoad()
  @BeforeCreate()
  @BeforeUpdate()
  generateFullName(): void {
    this.fullname = `${this.firstname ?? ''} ${this.lastname ?? ''}`.trim();
  }

  @ApiProperty({ description: 'Indique si une réinitialisation de mot de passe est en cours', example: false, default: false })
  @Property({ type: 'boolean', nullable: false, default: false })
  resetPasswordOngoing!: boolean;

  @ApiProperty({ description: 'Rôles de l\'utilisateur', enum: UserRoleEnum, isArray: true, example: [UserRoleEnum.User], default: [UserRoleEnum.User] })
  @Enum({ items: () => UserRoleEnum, array: true, default: [UserRoleEnum.User] })
  roles!: UserRoleEnum[];

  @ApiProperty({ description: 'Préférence pour le thème sombre', example: true, default: true })
  @Property({ type: 'boolean', nullable: false, default: true })
  preferDarkTheme!: boolean;

  @ApiProperty({ description: 'Indique si l\'utilisateur est administrateur (calculé automatiquement)', example: false, readOnly: true })
  @Expose()
  get isAdmin(): boolean {
    return this.roles.includes(UserRoleEnum.Admin);
  }

  // ****
  // ! Relations
  // ****
  
  @ApiProperty({ description: 'Informations d\'authentification JWT associées', type: () => UserJwt, nullable: true, required: false })
  @Index()
  @OneToOne(() => UserJwt, {
    cascade: [Cascade.ALL],
    eager: false,
    nullable: true,
    owner: true,
  })
  userJwt?: UserJwt;
}
