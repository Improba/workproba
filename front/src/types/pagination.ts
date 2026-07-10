/**
 * Response structure for paginated API calls
 */
export interface IPaginationResponse<Entity> {
  count: number;
  results: Entity[];
}

export type PaginationOrder = 'ASC' | 'DESC' | 'asc' | 'desc' | undefined;

/**
 * Base DTO for pagination requests
 * Matches backend PaginationDTO structure
 */
export interface IBasePaginationDTO {
  limit?: number;
  offset?: number;
  orderBy?: string;
  order: PaginationOrder;
  q?: string;
  populate?: string[];
}
