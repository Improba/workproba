import { Collection, Rel } from '@mikro-orm/core';
import {
  Entity,
  Index,
  ManyToOne,
  OneToMany,
  Property,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Project } from '@core/workspace/entities/project.entity';
import { Message } from '@core/session/entities/message.entity';

@Entity()
export class Session extends BaseEntity {
  @Index()
  @ManyToOne(() => Project)
  project!: Rel<Project>;

  @Property({ type: 'string', length: 255, nullable: true })
  title?: string | null;

  @Property({ type: 'json', nullable: true })
  metadata?: Record<string, unknown> | null;

  @OneToMany(() => Message, (message) => message.session)
  messages = new Collection<Message>(this);
}
