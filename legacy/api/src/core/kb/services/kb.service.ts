import { Injectable } from '@nestjs/common';
import { IndexDocumentDto } from '@core/kb/dtos/index-document.dto';
import { SearchKbDto } from '@core/kb/dtos/search-kb.dto';
import { EmbeddingRepository } from '@core/kb/repositories/embedding.repository';
import { LlmProviderRegistry } from '@core/llm-provider/services/llm-provider-registry.service';

@Injectable()
export class KbService {
  constructor(
    private readonly embeddingRepository: EmbeddingRepository,
    private readonly llmProviderRegistry: LlmProviderRegistry,
  ) {}

  async index(dto: IndexDocumentDto) {
    const provider = await this.llmProviderRegistry.resolve(dto.tenantId);
    const [vector] = await provider.embeddings({
      input: [dto.content],
    });

    return this.embeddingRepository.saveChunk({
      tenantId: dto.tenantId,
      projectId: dto.projectId,
      documentId: dto.documentId ?? null,
      chunkIndex: dto.chunkIndex,
      content: dto.content,
      vector,
    });
  }

  async search(dto: SearchKbDto) {
    const provider = await this.llmProviderRegistry.resolve(dto.tenantId);
    const [vector] = await provider.embeddings({
      input: [dto.query],
    });

    return this.embeddingRepository.searchNearest({
      tenantId: dto.tenantId,
      projectId: dto.projectId,
      vector,
      limit: dto.limit ?? 8,
    });
  }
}
