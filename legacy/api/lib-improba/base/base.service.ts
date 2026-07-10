
import { FilterQuery, FindOneOptions, QueryOrderMap } from '@mikro-orm/core';
import {
  BaseRepository,
  IPaginationOutput,
  IPaginationOptions,
  } from './base.repository';
import { BaseEntity } from './base.entity';


export class BaseService<Entity extends BaseEntity, Repository> {
  constructor(private readonly _repository: Repository) {}

  public async findOne(where: FilterQuery<Entity>): Promise<Entity | null> {
    return await (
      this._repository as unknown as BaseRepository<Entity>
    ).findOne(where);
  }

  public async findOneById(
    id: number,
    options?: FindOneOptions<Entity>,
  ): Promise<Entity | null> {
    return await (
      this._repository as unknown as BaseRepository<Entity>
    ).findOneById(id, options);
  }

  public async findAll(): Promise<Partial<Entity>[]> {
    // Using mikro orm, run a findAll with order by id DESC
    return await (
      this._repository as unknown as BaseRepository<Entity>
    ).findAll({
      orderBy: { id: 'DESC' } as QueryOrderMap<Entity>,
    });
  }

  public async delete(id: number): Promise<Entity | null> {
    return await (
      this._repository as unknown as BaseRepository<Entity>
    ).softDelete(id);
  }
}
