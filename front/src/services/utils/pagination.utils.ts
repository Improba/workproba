export interface IPaginationOptions {
  limit: number;
  offset: number;
  orderBy: string;
  order: string; // 'DESC' | 'ASC'
  include?: string[];
}

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
