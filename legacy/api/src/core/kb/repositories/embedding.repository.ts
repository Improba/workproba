import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { Tenant } from '@core/tenant/entities/tenant.entity';
import { Embedding } from '@core/kb/entities/embedding.entity';
import { Document } from '@core/workspace/entities/document.entity';
import { Project } from '@core/workspace/entities/project.entity';

export interface SaveEmbeddingChunkInput {
  tenantId: number;
  projectId: number;
  documentId?: number | null;
  chunkIndex: number;
  content: string;
  vector: number[];
}

export interface EmbeddingSearchInput {
  tenantId: number;
  projectId: number;
  vector: number[];
  limit: number;
}

export interface EmbeddingSearchRow {
  id: number;
  documentId: number | null;
  chunkIndex: number;
  content: string;
  score: number;
}

@BaseCustomRepository(Embedding)
export class EmbeddingRepository extends BaseRepository<Embedding> {
  async saveChunk(input: SaveEmbeddingChunkInput): Promise<Embedding> {
    const em = this.getEntityManager();
    const embedding = this.create({
      tenant: em.getReference(Tenant, input.tenantId),
      project: em.getReference(Project, input.projectId),
      document: input.documentId
        ? em.getReference(Document, input.documentId)
        : null,
      chunkIndex: input.chunkIndex,
      content: input.content,
      vector: input.vector,
    });

    return this.save(embedding);
  }

  /**
   * Native SQL stays in the repository because pgvector operators are not a
   * good fit for high-level ORM query builders.
   */
  async searchNearest(input: EmbeddingSearchInput): Promise<EmbeddingSearchRow[]> {
    const vectorLiteral = this.toVectorLiteral(input.vector);
    const sql = `
      select
        id,
        document_id as "documentId",
        chunk_index as "chunkIndex",
        content,
        1 - (vector <=> ?::vector) as score
      from embedding
      where tenant_id = ?
        and project_id = ?
        and deleted_at is null
      order by vector <=> ?::vector
      limit ?
    `;

    return this.getEntityManager().execute<EmbeddingSearchRow[]>(sql, [
      vectorLiteral,
      input.tenantId,
      input.projectId,
      vectorLiteral,
      input.limit,
    ]);
  }

  private toVectorLiteral(vector: number[]): string {
    return `[${vector.join(',')}]`;
  }
}
