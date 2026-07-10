import { IEntity } from '../utils/entity.interface';

export enum UserRoleEnum {
  Admin = 'admin',
  User = 'user',
}

export interface IUserJWT extends IEntity {
  username: string;
  activated: boolean;
  activationToken: string | null;
  forgetPasswordToken: string | null;
}

// TODO remove this
export interface IUser extends IEntity {
  firstname: string | null;
  lastname: string | null;
  fullname: string | null;
  resetPasswordOngoing: boolean;
  roles: UserRoleEnum[];
  preferDarkTheme?: boolean;
  isAdmin?: boolean;
  userJwt?: IUserJWT;
}
