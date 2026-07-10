import { Module } from '@nestjs/common';
import { BaseModule } from '@lib-improba/base/base.module';
import { TenantModule } from '@core/tenant/tenant.module';
import { LlmProviderController } from '@core/llm-provider/controllers/llm-provider.controller';
import { LlmProviderRepository } from '@core/llm-provider/repositories/llm-provider.repository';
import { LlmProviderRegistry } from '@core/llm-provider/services/llm-provider-registry.service';
import { LlmProviderService } from '@core/llm-provider/services/llm-provider.service';

@Module({
  imports: [TenantModule, BaseModule.forCustomRepository([LlmProviderRepository])],
  controllers: [LlmProviderController],
  providers: [LlmProviderRegistry, LlmProviderService],
  exports: [LlmProviderRegistry, LlmProviderService],
})
export class LlmProviderModule {}
