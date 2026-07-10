import { Rel } from '@mikro-orm/core';
import {
  Entity,
  Index,
  ManyToOne,
  Property,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Tenant } from '@core/tenant/entities/tenant.entity';
import { Document } from '@core/workspace/entities/document.entity';
import { Project } from '@core/workspace/entities/project.entity';

@Entity()
export class Embedding extends BaseEntity {
  @Index()
  @ManyToOne(() => Tenant)
  tenant!: Rel<Tenant>;

  @Index()
  @ManyToOne(() => Project)
  project!: Rel<Project>;

  @Index()
  @ManyToOne(() => Document, { nullable: true })
  document?: Rel<Document> | null;

  @Property({ type: 'integer' })
  chunkIndex!: number;

  @Property({ type: 'text' })
  content!: string;

  @Property({ columnType: 'vector(1536)', type: 'vector' })
  vector!: number[];
}
