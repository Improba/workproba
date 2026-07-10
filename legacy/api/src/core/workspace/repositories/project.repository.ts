import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { Project } from '@core/workspace/entities/project.entity';

@BaseCustomRepository(Project)
export class ProjectRepository extends BaseRepository<Project> {
  async findByTenant(tenantId: number): Promise<Project[]> {
    return this.find(
      { tenant: tenantId },
      {
        orderBy: { updatedAt: 'DESC' },
      },
    );
  }
}
