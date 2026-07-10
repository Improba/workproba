import { Module } from '@nestjs/common';
import { CronTasksModule } from './cron-tasks/cron-tasks.module';
import { BaseModule } from 'src/../lib-improba/base/base.module';
import { UsersModule } from './users/index.module';
import { AgentGatewayModule } from '@core/agent-gateway/agent-gateway.module';
import { KbModule } from '@core/kb/kb.module';
import { LlmProviderModule } from '@core/llm-provider/llm-provider.module';
import { SessionModule } from '@core/session/session.module';
import { TenantModule } from '@core/tenant/tenant.module';
import { WorkspaceModule } from '@core/workspace/workspace.module';

@Module({
  imports: [
    BaseModule.forCustomRepository([]),
    TenantModule,
    WorkspaceModule,
    SessionModule,
    LlmProviderModule,
    KbModule,
    AgentGatewayModule,
    CronTasksModule,
    UsersModule,
  ],
  controllers: [ ],
  providers: [],
})
export class CoreModule {}
