import { Module } from '@nestjs/common';
import { KbModule } from '@core/kb/kb.module';
import { SessionModule } from '@core/session/session.module';
import { AgentGatewayController } from '@core/agent-gateway/controllers/agent-gateway.controller';
import { AgentGatewayService } from '@core/agent-gateway/services/agent-gateway.service';

@Module({
  imports: [SessionModule, KbModule],
  controllers: [AgentGatewayController],
  providers: [AgentGatewayService],
  exports: [AgentGatewayService],
})
export class AgentGatewayModule {}
