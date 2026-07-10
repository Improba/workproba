import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { Document } from '@core/workspace/entities/document.entity';

@BaseCustomRepository(Document)
export class DocumentRepository extends BaseRepository<Document> {
  async findByProject(projectId: number): Promise<Document[]> {
    return this.find(
      { project: projectId },
      {
        orderBy: { createdAt: 'DESC' },
      },
    );
  }
}
