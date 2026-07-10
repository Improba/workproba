import { IBasePaginationDTO } from '#types/pagination';
import { EUserRole } from '#types/enums';
export interface IPaginateUserDTO extends IBasePaginationDTO {
  role?: EUserRole;
}
