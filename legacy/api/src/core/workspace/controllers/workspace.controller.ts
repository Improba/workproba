import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { ApiConsumes, ApiTags } from '@nestjs/swagger';
import { BaseController } from '@lib-improba/base/base.controller';
import { CreateProjectDto } from '@core/workspace/dtos/create-project.dto';
import { UploadDocumentDto } from '@core/workspace/dtos/upload-document.dto';
import { WorkspaceService } from '@core/workspace/services/workspace.service';

@ApiTags('workspaces')
@Controller()
export class WorkspaceController extends BaseController {
  constructor(private readonly workspaceService: WorkspaceService) {
    super();
  }

  @Post('tenants/:tenantId/projects')
  async createProject(
    @Param('tenantId', ParseIntPipe) tenantId: number,
    @Body() dto: CreateProjectDto,
  ) {
    return this.workspaceService.createProject(tenantId, dto);
  }

  @Get('tenants/:tenantId/projects')
  async listProjects(@Param('tenantId', ParseIntPipe) tenantId: number) {
    return this.workspaceService.listProjects(tenantId);
  }

  @Post('projects/:projectId/documents')
  @ApiConsumes('multipart/form-data')
  @UseInterceptors(FileInterceptor('file'))
  async uploadDocument(
    @Param('projectId', ParseIntPipe) projectId: number,
    @Body() dto: UploadDocumentDto,
    @UploadedFile() file?: Express.Multer.File,
  ) {
    return this.workspaceService.registerUploadedDocument(projectId, dto, file);
  }

  @Get('projects/:projectId/documents')
  async listDocuments(@Param('projectId', ParseIntPipe) projectId: number) {
    return this.workspaceService.listDocuments(projectId);
  }
}
