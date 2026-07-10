import { EUserRole } from '#types/enums';

export interface IAdminUpdateUserDTO {
  id: number
  roles: EUserRole[];
}
