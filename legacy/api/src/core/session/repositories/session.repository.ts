import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { Session } from '@core/session/entities/session.entity';

@BaseCustomRepository(Session)
export class SessionRepository extends BaseRepository<Session> {
  async findByProject(projectId: number): Promise<Session[]> {
    return this.find(
      { project: projectId },
      {
        orderBy: { updatedAt: 'DESC' },
      },
    );
  }
}
