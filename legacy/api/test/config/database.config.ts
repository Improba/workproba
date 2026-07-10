import { defineConfig } from '@mikro-orm/postgresql';
import { TsMorphMetadataProvider } from '@mikro-orm/reflection';
import { config } from 'dotenv';
import * as path from 'node:path';

config();

/**
 * Configuration MikroORM pour les tests e2e PostgreSQL.
 * Utilise une base dédiée suffixée par `_test`.
 */
export function createTestDatabaseConfig() {
  const database = `${process.env.DB_NAME}_test`;

  return defineConfig({
    metadataProvider: TsMorphMetadataProvider,
    host: process.env.DB_HOST,
    port: parseInt(process.env.DB_PORT ?? '5432', 10),
    user: process.env.DB_USERNAME,
    password: process.env.DB_PASSWORD,
    dbName: database,
    entities: [
      path.join(__dirname, '../../src/**/*.entity{.ts,.js}'),
      path.join(__dirname, '../../lib-improba/**/*.entity{.ts,.js}'),
    ],
    entitiesTs: [
      path.join(__dirname, '../../src/**/*.entity.ts'),
      path.join(__dirname, '../../lib-improba/**/*.entity.ts'),
    ],
    allowGlobalContext: true,
    debug: false,
    filters: {},
  });
}

export const testDatabaseConfig = createTestDatabaseConfig();
