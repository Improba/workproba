import { Module } from '@nestjs/common';
import { BaseModule } from '@lib-improba/base/base.module';
import { TenantController } from '@core/tenant/controllers/tenant.controller';
import { TenantRepository } from '@core/tenant/repositories/tenant.repository';
import { TenantService } from '@core/tenant/services/tenant.service';

@Module({
  imports: [BaseModule.forCustomRepository([TenantRepository])],
  controllers: [TenantController],
  providers: [TenantService],
  exports: [TenantService],
})
export class TenantModule {}
