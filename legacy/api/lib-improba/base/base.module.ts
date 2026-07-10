import { DynamicModule, Provider } from '@nestjs/common';
import { EntityManager } from '@mikro-orm/core';
import { BASE_CUSTOM_REPOSITORY } from '../decorators';

export class BaseModule {
  public static forCustomRepository<T extends new (...args: any[]) => any>(
    repositories: T[],
  ): DynamicModule {
    const providers: Provider[] = [];

    for (const repository of repositories) {
      const entity = Reflect.getMetadata(
        BASE_CUSTOM_REPOSITORY,
        repository,
      );

      if (!entity) {
        continue;
      }

      providers.push({
        inject: [EntityManager],
        provide: repository,
        useFactory: (em: EntityManager): typeof repository => {
          // MikroORM's EntityManager can provide the repository for an entity.
          // We instantiate the custom repository by passing EntityManager so the
          // repository class can leverage it internally.
          return new repository(em as any, entity);
        },
      });
    }

    return {
      exports: providers,
      module: BaseModule,
      providers,
    };
  }
}
