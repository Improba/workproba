import { Module } from '@nestjs/common';
import { AuthJwtModule } from './auth-jwt/auth-jwt.module';

@Module({
  imports: [
    AuthJwtModule,
  ],
  exports: [],
})
export class LibImprobaModules {}