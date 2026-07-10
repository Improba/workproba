import { EntityManager, MikroORM } from '@mikro-orm/core';
import { config } from 'dotenv';
import { testDatabaseConfig } from './config/database.config';

config();

/**
 * Vide toutes les tables de la base de test sauf la table des migrations.
 */
export async function truncateAllTables(em: EntityManager): Promise<void> {
  const tables = await em.getConnection().execute(`
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename != 'mikro_orm_migrations'
  `);

  if ((tables as Array<unknown>).length === 0) {
    return;
  }

  const tableNames = (tables as Array<{ tablename: string }>)
    .map((row) => `"${row.tablename}"`)
    .join(', ');

  await em
    .getConnection()
    .execute(`TRUNCATE TABLE ${tableNames} RESTART IDENTITY CASCADE;`);
}

let schemaInitialized = false;
let schemaInitPromise: Promise<void> | null = null;

/**
 * Initialise la DB de test une seule fois et nettoie les tables.
 */
export async function initTestDatabase(): Promise<MikroORM> {
  if (!schemaInitialized) {
    if (!schemaInitPromise) {
      schemaInitPromise = (async () => {
        const tempOrm = await MikroORM.init(testDatabaseConfig as any);

        try {
          await tempOrm.schema.create();
        } catch (error: unknown) {
          const errorMessage =
            error instanceof Error ? error.message : String(error);

          if (
            !errorMessage.includes('already exists') &&
            !errorMessage.includes('duplicate key') &&
            !errorMessage.includes('duplicate key value')
          ) {
            throw error;
          }
        }

        await tempOrm.close();
        schemaInitialized = true;
        schemaInitPromise = null;
      })();
    }

    await schemaInitPromise;
  }

  const orm = await MikroORM.init(testDatabaseConfig as any);
  const em = orm.em.fork();
  await truncateAllTables(em);

  return orm;
}

export async function closeTestDatabase(orm: MikroORM): Promise<void> {
  await orm.close(true);
}

/**
 * Génère un identifiant unique pour les données de test.
 */
export function generateUniqueId(prefix = ''): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 7);
  return prefix ? `${prefix}-${timestamp}-${random}` : `${timestamp}-${random}`;
}
