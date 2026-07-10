import { EntityRepository, EntityManager, FilterQuery, QueryOrderMap } from '@mikro-orm/postgresql';
import { Collection, FindOneOptions, LoadStrategy, wrap, WrappedEntity } from '@mikro-orm/core';
import { InternalServerErrorException } from '@nestjs/common';

/**
 * Interface to define the pagination output.
 * This is used to return the pagination output from the repository.
 */
export interface IPaginationOutput<Entity> {
  count: number;
  results: Entity[];
  }
  
/**
 * Interface to define the pagination options.
 * This is used to pass the pagination options to the repository.
 */
export interface IPaginationOptions<Entity> {
  where?: FilterQuery<Entity>;
  limit?: number;
  offset?: number;
  orderBy?: QueryOrderMap<Entity>;
  populate?: string[];
}

export class BaseRepository<Entity extends object> extends EntityRepository<Entity> {
  
  async save(entity: Entity | Partial<Entity>): Promise<Entity> {
    let ref: Entity | null = null;

    const isEntityInitialized = wrap(entity as any).isInitialized?.();
    const hasEntityId = (<any>entity).id;

    if (hasEntityId && !isEntityInitialized) {
      const entityInDb = await this.findOneById(hasEntityId);
      if (entityInDb) {
        ref = wrap(entityInDb).assign(entity as any, { ignoreUndefined: true }) as Entity;
      }
    }

    if (!ref) {
      ref = isEntityInitialized || hasEntityId ? (entity as any) : this.create(entity as any);
    }

    const em = this.getEntityManager();
    em.persist(<Entity>ref);
    await em.flush();

    return ref as Entity;
  }

  /**
   * Soft delete an entity.
   * @param idOrEntity - The id or entity to soft delete.
   * @returns The entity soft deleted or null if not found.
   */
  async softDelete(idOrEntity: number | string | Entity): Promise<Entity | null> {
    const entity = typeof idOrEntity === 'object' ? idOrEntity : await this.findOne({ id: idOrEntity } as any);
    if (entity && (entity as any).deletedAt === undefined) {
      // entity not soft deletable
      throw new InternalServerErrorException('Entity not soft deletable');
    }

    if (entity) {
      (entity as any).deletedAt = new Date();
      const em = this.getEntityManager();
      em.persist(entity as any);
      await em.flush();
    }

    return entity;
  }

  /**
   * Delete an entity.
   * @param idOrEntity - The id or entity to delete.
   * @returns The entity deleted or null if not found.
   */
  async hardDelete(idOrEntity: number | string | Entity): Promise<Entity | null> {
    const entity = typeof idOrEntity === 'object' ? idOrEntity : await this.findOne({ id: idOrEntity } as any);
    if (entity) {
      const em = this.getEntityManager();
      em.remove(entity as any);
      await em.flush();
    }
    return entity;
  }

  async softRemove(entity: Entity): Promise<void> {
    await this.softDelete(entity);
  }

  async findAndPaginate(options: IPaginationOptions<Entity>): Promise<IPaginationOutput<Entity>> {
    const limit = options.limit ?? 50;
    const offset = options.offset ?? 0;
    const [results, count] = await this.findAndCount(options.where ?? {}, {
      populate: options.populate as any,
      limit,
      offset,
      orderBy: options.orderBy,
    });

    return { count, results };
  }

  /**
   * Find one entity by id.
   * Example: const user = await userRepository.findOneById(123, { populate: ['profile', 'roles']});
   * @param id - The id of the entity to find.
   * @param options - The options to pass to the findOne method.
   * @returns The entity found or null if not found.
   */
  async findOneById(id: number, options?: FindOneOptions<Entity>): Promise<Entity | null> {
    return this.findOne({ id } as any, options);
  }

  async update(id: number, data: Partial<Entity>): Promise<Entity> {
    const entity = await this.findOneById(id);
    if (!entity) {
      throw new Error('Entity not found');
    }
    Object.assign(entity, data);
    const em = this.getEntityManager();
    em.persist(entity);
    await em.flush();
    return entity;
  }
}