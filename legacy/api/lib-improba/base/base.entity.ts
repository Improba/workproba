import {
  PrimaryKey,
  Property,
  Filter,
} from '@mikro-orm/decorators/legacy';
import { BigIntNumberType } from './bigint-number.type';

// Import conditionnel de ApiProperty pour éviter les erreurs lors des migrations CLI
let ApiProperty: any;
try {
  ApiProperty = require('@nestjs/swagger').ApiProperty;
} catch (e) {
  // Si @nestjs/swagger n'est pas disponible (ex: migrations CLI), utiliser un décorateur vide
  ApiProperty = () => () => {};
}

/**
 * Base entity providing an auto-increment bigint primary key together with common timestamp columns.
 * MikroORM maps Postgres `bigint` values to JavaScript `string` by default – we deliberately keep it as
 * `string` here to avoid losing precision beyond 53-bit.  If you need a number, cast explicitly where
 * you read the property (e.g. `Number(entity.id)`).
 */
@Filter({ name: 'softDelete', cond: { deletedAt: null } })
export abstract class BaseEntity {
  /**
   * The primary key of the entity.
   * It is an auto-increment bigint.
   * It is mapped to the `id` column of the database.
   * It is a string by default, because of big int that can only be represented as string.
   * BUT, we have a kind of proxy that will convert the string to a number, with an error 
   * if the number is too big for the js Number.MAX_SAFE_INTEGER (see: bigint-number.type.ts).
   * Autoincrement is set to true, so the database will automatically increment the id.
   */
  @ApiProperty({ description: 'Identifiant unique de l\'entité (bigint)', example: 1, type: Number })
  @PrimaryKey({ type: BigIntNumberType, autoincrement: true })
  id!: number; // bigint → number

  // Postgres timestamp with timezone
  // Indicate the creation date of the entity
  @ApiProperty({ description: 'Date de création de l\'entité', example: '2024-01-01T00:00:00.000Z', type: Date, required: false })
  @Property({ type: 'timestamp', onCreate: () => new Date() })
  createdAt?: Date = new Date();

  // Indicate the last update date of the entity
  @ApiProperty({ description: 'Date de dernière modification de l\'entité', example: '2024-01-01T00:00:00.000Z', type: Date, required: false })
  @Property({ type: 'timestamp', onUpdate: () => new Date() })
  updatedAt?: Date = new Date();

  // Indicate the soft deletion date of the entity
  // The mere presence of this field in the entity means that the entity is soft deletable
  @ApiProperty({ description: 'Date de suppression (soft delete)', example: null, type: Date, nullable: true, required: false })
  @Property({ type: 'timestamp', nullable: true })
  deletedAt?: Date | null;
}