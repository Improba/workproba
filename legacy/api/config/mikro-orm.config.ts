import { defineConfig } from '@mikro-orm/postgresql';
import { TsMorphMetadataProvider } from '@mikro-orm/reflection';
import { config } from 'dotenv';
import 'reflect-metadata';
import * as fs   from 'node:fs';
import * as path from 'node:path';

config();

/** Convert `AuthJwtModule` → `auth-jwt` */
function toKebabDir(modClass: { name: string }) {
  return modClass.name
    .replace(/Module$/, '')               // drop the "Module" suffix
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .toLowerCase();
}

////////////////////////////////////////////////////////////////////////////////
// 1. helper – synchronous directory walk
////////////////////////////////////////////////////////////////////////////////
function walkDir(dir: string, onFile: (file: string) => void) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    entry.isDirectory() ? walkDir(full, onFile) : onFile(full);
  }
}

////////////////////////////////////////////////////////////////////////////////
// 2. scan the given roots for every *.entity.* file
////////////////////////////////////////////////////////////////////////////////
function findAllEntityFiles(roots: string[]) {
  const ts: string[] = [];
  const js: string[] = [];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    walkDir(root, (file) => {
      if (file.endsWith('.entity.ts')) ts.push(file);
      if (file.endsWith('.entity.js')) js.push(file);
    });
  }
  return { ts, js };
}

////////////////////////////////////////////////////////////////////////////////
// 3. recursively collect every module reachable from AppModule
////////////////////////////////////////////////////////////////////////////////
function discoverEnabledModuleDirs(appModulePath: string) {
  // Load app.module – the loader (ts-node / @swc-node/register) is already
  // registered by the CLI runner. If this fails (typically due to a circular
  // import when this config is itself imported by app.module), we return an
  // empty set so the caller falls back to broad entity globs.
  let AppModule: any;
  try {
    ({ AppModule } = require(appModulePath));
  } catch {
    return new Set<string>();
  }
  if (!AppModule) return new Set<string>();
  const queue: any[] = [AppModule];
  const visited       = new Set<any>();
  const enabledDirs   = new Set<string>();

  /** locate the file in require.cache that exported the given class */
  function findDeclaringFile(modClass: any): string | null {
    const cacheValues = Object.values(require.cache || {}) as Array<any | undefined>;
    for (const m of cacheValues) {
      try {
        // direct export  (module.exports = MyModule)
        if (m && m.exports === modClass)            return m.filename;
        // named export  (exports.MyModule = MyModule)
        if (m && typeof m.exports === 'object') {
          // Use try-catch to handle cases where accessing exports triggers getters
          // that may access Express request objects (e.g., Swagger decorators)
          try {
            const exportsValues = Object.values(m.exports);
            for (const v of exportsValues) {
              if (v === modClass) return m.filename;
            }
          } catch (e) {
            // Skip modules that throw errors when accessing exports
            // This can happen with Swagger decorators that access request.protocol
            continue;
          }
        }
      } catch (e) {
        // Skip modules that throw errors during inspection
        continue;
      }
    }
    return null;
  }

  const libImprobaRoot = path.join(__dirname, '..', 'lib-improba', 'modules');

  while (queue.length) {
    const mod = queue.shift();
    if (!mod || visited.has(mod)) continue;
    visited.add(mod);

    const file = findDeclaringFile(mod);
    if (file) {
      const dirname = path.dirname(file);
      if (dirname.startsWith(libImprobaRoot)) {
        // For lib-improba, narrow to the concrete module directory (avoid aggregator folder)
        const candidate = path.join(libImprobaRoot, toKebabDir(mod as { name: string }));
        if (fs.existsSync(candidate)) {
          enabledDirs.add(candidate);
        }
      } else {
        enabledDirs.add(dirname);
      }
    }

    const imports = Reflect.getMetadata('imports', mod) ?? [];
    queue.push(...imports);
  }
  return enabledDirs;
}

////////////////////////////////////////////////////////////////////////////////
// 4. glue everything together
////////////////////////////////////////////////////////////////////////////////
function resolveAppModulePath(): string {
  // When running via ts-node (CLI), we want the TS source; for built app, use JS.
  const tsPath = path.join(__dirname, '..', 'src', 'app.module.ts');
  const jsPath = path.join(__dirname, '..', 'src', 'app.module.js');
  const distJs = path.join(__dirname, '..', 'src', 'app.module.cjs');
  if (fs.existsSync(tsPath)) return tsPath;
  if (fs.existsSync(jsPath)) return jsPath;
  if (fs.existsSync(distJs)) return distJs;
  // final fallback for standard Nest build layout
  const built = path.join(__dirname, '..', 'dist', 'src', 'app.module.js');
  return built;
}

const ROOTS         = [path.join(__dirname, '..', 'src'),
                       path.join(__dirname, '..', 'lib-improba')];

const allEntities    = findAllEntityFiles(ROOTS);
const enabledDirs    = discoverEnabledModuleDirs(resolveAppModulePath());

const entitiesTs = allEntities.ts.filter((f) =>
  Array.from(enabledDirs).some((dir) => f.startsWith(dir + path.sep)),
);
const entities   = allEntities.js.filter((f) =>
  Array.from(enabledDirs).some((dir) => f.startsWith(dir + path.sep)),
);

// Fallback – CLI under ts-node usually has no compiled JS yet
const runtimeEntities = entities.length ? entities : entitiesTs;

// Strong fallback for Nest runtime: if nothing detected, use broad globs
const finalEntities = runtimeEntities.length
  ? runtimeEntities
  : [
      path.join(__dirname, '..', 'src', '**', '*.entity.js'),
      path.join(__dirname, '..', 'lib-improba', 'modules', '**', '*.entity.js'),
    ];
const finalEntitiesTs = entitiesTs.length
  ? entitiesTs
  : [
      path.join(__dirname, '..', 'src', '**', '*.entity.ts'),
      path.join(__dirname, '..', 'lib-improba', 'modules', '**', '*.entity.ts'),
    ];

// Log the actual set that MikroORM will use (after fallbacks)
//console.log('entitiesInUse', finalEntities);

////////////////////////////////////////////////////////////////////////////////
// 5. Mikro ORM configuration (leave everything else unchanged)
////////////////////////////////////////////////////////////////////////////////
const mikroOrmConfig = defineConfig({
  metadataProvider: TsMorphMetadataProvider,
  host: process.env.DB_HOST,
  port: process.env.DB_PORT ? parseInt(process.env.DB_PORT, 10) : 5432,
  user: process.env.DB_USERNAME,
  password: process.env.DB_PASSWORD,
  dbName: process.env.DB_NAME,
  entities   : finalEntities,
  entitiesTs : finalEntitiesTs,
  debug: false,
  migrations: {
    path: 'migrations',
    tableName: 'mikro_orm_migrations',
    transactional: true,
    emit: 'ts',
  },
  // Filters are used to filter out soft deleted entities.
  // To override it, you may do: em.setFilter('softDelete', false);
  filters: {
    softDelete: {
      cond: { deletedAt: null },
    },
  },
  extensions: [/* eslint-disable @typescript-eslint/no-var-requires */ require('@mikro-orm/migrations').Migrator],
});

export default mikroOrmConfig; 