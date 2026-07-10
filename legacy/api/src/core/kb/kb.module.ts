import { Module } from '@nestjs/common';
import { BaseModule } from '@lib-improba/base/base.module';
import { LlmProviderModule } from '@core/llm-provider/llm-provider.module';
import { KbController } from '@core/kb/controllers/kb.controller';
import { EmbeddingRepository } from '@core/kb/repositories/embedding.repository';
import { KbService } from '@core/kb/services/kb.service';

@Module({
  imports: [
    LlmProviderModule,
    BaseModule.forCustomRepository([EmbeddingRepository]),
  ],
  controllers: [KbController],
  providers: [KbService],
  exports: [KbService],
})
export class KbModule {}
