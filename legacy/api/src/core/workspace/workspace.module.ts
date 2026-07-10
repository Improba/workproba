import { Module } from '@nestjs/common';
import { BaseModule } from '@lib-improba/base/base.module';
import { TenantModule } from '@core/tenant/tenant.module';
import { WorkspaceController } from '@core/workspace/controllers/workspace.controller';
import { DocumentRepository } from '@core/workspace/repositories/document.repository';
import { ProjectRepository } from '@core/workspace/repositories/project.repository';
import { WorkspaceService } from '@core/workspace/services/workspace.service';

@Module({
  imports: [
    TenantModule,
    BaseModule.forCustomRepository([ProjectRepository, DocumentRepository]),
  ],
  controllers: [WorkspaceController],
  providers: [WorkspaceService],
  exports: [WorkspaceService],
})
export class WorkspaceModule {}
