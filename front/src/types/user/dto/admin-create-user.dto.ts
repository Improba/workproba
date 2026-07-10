import { EUserRole } from '#types/enums';

export interface IAdminCreateUserDTO {
  firstname?: string;
  lastname?: string;

  roles: EUserRole[];

  userJwt: {
    username: string;
    password: string;
  };
}
