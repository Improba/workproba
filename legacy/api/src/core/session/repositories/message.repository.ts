import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { Message } from '@core/session/entities/message.entity';

@BaseCustomRepository(Message)
export class MessageRepository extends BaseRepository<Message> {
  async findBySession(sessionId: number): Promise<Message[]> {
    return this.find(
      { session: sessionId },
      {
        orderBy: { createdAt: 'ASC' },
      },
    );
  }
}
