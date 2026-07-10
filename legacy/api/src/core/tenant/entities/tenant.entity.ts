import { Collection } from '@mikro-orm/core';
import {
  Entity,
  Index,
  OneToMany,
  Property,
  Unique,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Project } from '@core/workspace/entities/project.entity';
import { LlmProvider } from '@core/llm-provider/entities/llm-provider.entity';

@Entity()
export class Tenant extends BaseEntity {
  @Property({ type: 'string', length: 200 })
  name!: string;

  @Unique()
  @Index()
  @Property({ type: 'string', length: 120 })
  slug!: string;

  @Property({ type: 'boolean', default: true })
  isActive: boolean = true;

  @OneToMany(() => Project, (project) => project.tenant)
  projects = new Collection<Project>(this);

  @OneToMany(() => LlmProvider, (provider) => provider.tenant)
  llmProviders = new Collection<LlmProvider>(this);
}
