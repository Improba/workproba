import { Collection, Rel } from '@mikro-orm/core';
import {
  Entity,
  Index,
  ManyToOne,
  OneToMany,
  Property,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Tenant } from '@core/tenant/entities/tenant.entity';
import { Document } from '@core/workspace/entities/document.entity';
import { Session } from '@core/session/entities/session.entity';

@Entity()
export class Project extends BaseEntity {
  @Index()
  @ManyToOne(() => Tenant)
  tenant!: Rel<Tenant>;

  @Property({ type: 'string', length: 200 })
  name!: string;

  @Index()
  @Property({ type: 'string', length: 120 })
  slug!: string;

  @Property({ type: 'text', nullable: true })
  description?: string | null;

  @Property({ type: 'string', length: 500, nullable: true })
  objectStoragePrefix?: string | null;

  @OneToMany(() => Document, (document) => document.project)
  documents = new Collection<Document>(this);

  @OneToMany(() => Session, (session) => session.project)
  sessions = new Collection<Session>(this);
}
