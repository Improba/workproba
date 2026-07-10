import { Rel } from '@mikro-orm/core';
import {
  Entity,
  Enum,
  Index,
  ManyToOne,
  Property,
} from '@mikro-orm/decorators/legacy';
import { BaseEntity } from '@lib-improba/base/base.entity';
import { Project } from '@core/workspace/entities/project.entity';

export enum DocumentStatusEnum {
  Uploaded = 'uploaded',
  Indexing = 'indexing',
  Indexed = 'indexed',
  Failed = 'failed',
}

@Entity()
export class Document extends BaseEntity {
  @Index()
  @ManyToOne(() => Project)
  project!: Rel<Project>;

  @Property({ type: 'string', length: 255 })
  filename!: string;

  @Property({ type: 'string', length: 120, nullable: true })
  mimeType?: string | null;

  @Property({ type: 'bigint' })
  sizeBytes!: number;

  @Property({ type: 'string', length: 1000 })
  storagePath!: string;

  @Enum({ items: () => DocumentStatusEnum, default: DocumentStatusEnum.Uploaded })
  status: DocumentStatusEnum = DocumentStatusEnum.Uploaded;

  @Property({ type: 'json', nullable: true })
  metadata?: Record<string, unknown> | null;

  @Property({ type: 'timestamp', nullable: true })
  indexedAt?: Date | null;
}
