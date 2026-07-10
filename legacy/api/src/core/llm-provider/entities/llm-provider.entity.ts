import { Rel } from '@mikro-orm/core';
import {
  Entity,
  Enum,
  Index,
  ManyToOne,
  Property,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Tenant } from '@core/tenant/entities/tenant.entity';

export enum LlmProviderKindEnum {
  OpenAICompatible = 'openai-compatible',
  Mistral = 'mistral',
}

@Entity()
export class LlmProvider extends BaseEntity {
  @Property({ type: 'string', length: 120 })
  name!: string;

  @Enum({ items: () => LlmProviderKindEnum })
  kind!: LlmProviderKindEnum;

  @Property({ type: 'string', length: 500, nullable: true })
  baseUrl?: string | null;

  @Property({ type: 'string', length: 500, nullable: true })
  apiKey?: string | null;

  @Property({ type: 'string', length: 200, nullable: true })
  defaultModel?: string | null;

  @Property({ type: 'string', length: 200, nullable: true })
  embeddingModel?: string | null;

  @Property({ type: 'boolean', default: true })
  isActive: boolean = true;

  @Index()
  @ManyToOne(() => Tenant, { nullable: true })
  tenant?: Rel<Tenant> | null;
}
