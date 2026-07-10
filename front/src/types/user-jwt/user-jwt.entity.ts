import type { IBaseEntity } from '#types/base.entity';

export interface IUserJwt extends IBaseEntity {
  username: string;
  activated: boolean;
  lastResetPasswordAt: Date | null;
}
