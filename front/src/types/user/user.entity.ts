import type { IBaseEntity } from '#types/base.entity';
import type { IUserJwt } from '#types/user-jwt/user-jwt.entity';
import type { EUserRole } from '#types/enums';

export interface IUser extends IBaseEntity {
  firstname: string;
  lastname: string;
  fullname?: string | null;
  resetPasswordOngoing: boolean;
  roles: EUserRole[];
  userJwt?: IUserJwt;
  preferDarkTheme?: boolean;
  isAdmin?: boolean;
}
