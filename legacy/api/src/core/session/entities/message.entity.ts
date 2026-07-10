import { Rel } from '@mikro-orm/core';
import {
  Entity,
  Enum,
  Index,
  ManyToOne,
  Property,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Session } from '@core/session/entities/session.entity';

export enum MessageRoleEnum {
  System = 'system',
  User = 'user',
  Assistant = 'assistant',
  Tool = 'tool',
}

@Entity()
export class Message extends BaseEntity {
  @Index()
  @ManyToOne(() => Session)
  session!: Rel<Session>;

  @Enum({ items: () => MessageRoleEnum })
  role!: MessageRoleEnum;

  @Property({ type: 'text' })
  content!: string;

  @Index()
  @Property({ type: 'bigint', nullable: true })
  parentId?: number | null;

  @Property({ type: 'string', length: 120, nullable: true })
  providerMessageId?: string | null;

  @Property({ type: 'json', nullable: true })
  metadata?: Record<string, unknown> | null;
}
