import { IBasePaginationDTO, IPaginationResponse } from '#types/pagination';

export type TablePagination = Omit<IBasePaginationDTO, 'q' | 'populate'>;

export type FetchFn<T> = (
  pagination: TablePagination,
  filters?: Record<string, any>
) => Promise<IPaginationResponse<T>>;

