import {
  BadRequestException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { TenantService } from '@core/tenant/services/tenant.service';
import { CreateProjectDto } from '@core/workspace/dtos/create-project.dto';
import { UploadDocumentDto } from '@core/workspace/dtos/upload-document.dto';
import { DocumentStatusEnum } from '@core/workspace/entities/document.entity';
import { Project } from '@core/workspace/entities/project.entity';
import { DocumentRepository } from '@core/workspace/repositories/document.repository';
import { ProjectRepository } from '@core/workspace/repositories/project.repository';

@Injectable()
export class WorkspaceService {
  constructor(
    private readonly projectRepository: ProjectRepository,
    private readonly documentRepository: DocumentRepository,
    private readonly tenantService: TenantService,
  ) {}

  async createProject(
    tenantId: number,
    dto: CreateProjectDto,
  ): Promise<Project> {
    const tenant = await this.tenantService.requireTenant(tenantId);
    const project = this.projectRepository.create({
      ...dto,
      tenant,
      objectStoragePrefix: `${tenant.slug}/${dto.slug}`,
    });

    return this.projectRepository.save(project);
  }

  async listProjects(tenantId: number): Promise<Project[]> {
    await this.tenantService.requireTenant(tenantId);
    return this.projectRepository.findByTenant(tenantId);
  }

  async requireProject(projectId: number): Promise<Project> {
    const project = await this.projectRepository.findOneById(projectId, {
      populate: ['tenant'],
    });
    if (!project) {
      throw new NotFoundException(`Project ${projectId} not found`);
    }

    return project;
  }

  async registerUploadedDocument(
    projectId: number,
    dto: UploadDocumentDto,
    file?: Express.Multer.File,
  ) {
    const project = await this.requireProject(projectId);
    const filename = dto.filename ?? file?.originalname;
    if (!filename) {
      throw new BadRequestException('Document filename is required');
    }

    // TODO: wire the object storage adapter and replace this deterministic path.
    const storagePath =
      dto.storagePath ?? `${project.objectStoragePrefix ?? project.id}/${filename}`;

    const document = this.documentRepository.create({
      project,
      filename,
      mimeType: file?.mimetype ?? null,
      sizeBytes: file?.size ?? 0,
      storagePath,
      status: DocumentStatusEnum.Uploaded,
      metadata: dto.metadata ?? null,
    });

    return this.documentRepository.save(document);
  }

  async listDocuments(projectId: number) {
    await this.requireProject(projectId);
    return this.documentRepository.findByProject(projectId);
  }
}
