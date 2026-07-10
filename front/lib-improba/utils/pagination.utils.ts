import { UnknownValues } from './type-aliases.utils';
export interface PaginationResponse<Entity> {
  count: number;
  results: Entity[];
}

export type PaginationFunction<Entity> = (
  limit: number,
  offset: number,
  orderBy?: string,
  order?: string,
  includes?: string[]
) => Promise<PaginationResponse<Entity>>;

export interface PaginationOptions {
  limit: number;
  offset: number;
  orderBy?: string;
  order?: string;
  includes?: string[];
}
