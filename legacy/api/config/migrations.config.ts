// ormconfig-migrations.ts
import { type Options } from '@mikro-orm/postgresql';
import { config } from 'dotenv';
import mikroOrmConfig from './mikro-orm.config';
import { Migrator as BaseMigrator, MigrationResult } from '@mikro-orm/migrations';

config();

/**
 * Extend the built-in Migrator to parse the migration name
 * to transform '-' to '_' in the migration name.
 */
class CustomMigrator extends BaseMigrator {
  /**
   * Register this migrator so the CLI uses it instead of the default one.
   * This overrides the static register() from BaseMigrator that always
   * registers the base class. By re-implementing we ensure that the factory
   * instantiates our subclass.
   */
  static override register(orm: import('@mikro-orm/core').MikroORM<any>): void {
    // use `this` so the correct subclass is instantiated
    orm.config.registerExtension('@mikro-orm/migrator', () => new this(orm.em));
  }
  override async create(
    path?: string,
    blank?: boolean,
    initial?: boolean,
    name?: string,
  ): Promise<MigrationResult> {
    const fixedName = name?.replace(/-/g, '_');

    return super.create(path, blank, initial, fixedName);
  }
}

export default {
  ...mikroOrmConfig,
  metadataCache: {
    // Disable metadata cache, this may slow down the migrations
    // But it will avoid the creation of a temp folder
    enabled: false,
  },
  extensions: [
    CustomMigrator,
  ]
 } as Options;
