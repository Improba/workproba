import { Module } from '@nestjs/common';
import { BaseModule } from '@lib-improba/base/base.module';
import { WorkspaceModule } from '@core/workspace/workspace.module';
import { SessionController } from '@core/session/controllers/session.controller';
import { MessageRepository } from '@core/session/repositories/message.repository';
import { SessionRepository } from '@core/session/repositories/session.repository';
import { SessionService } from '@core/session/services/session.service';

@Module({
  imports: [
    WorkspaceModule,
    BaseModule.forCustomRepository([SessionRepository, MessageRepository]),
  ],
  controllers: [SessionController],
  providers: [SessionService],
  exports: [SessionService],
})
export class SessionModule {}
