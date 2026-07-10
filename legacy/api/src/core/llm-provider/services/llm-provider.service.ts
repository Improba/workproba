import { Injectable } from '@nestjs/common';
import { TenantService } from '@core/tenant/services/tenant.service';
import { CreateLlmProviderDto } from '@core/llm-provider/dtos/create-llm-provider.dto';
import { LlmProvider } from '@core/llm-provider/entities/llm-provider.entity';
import { LlmProviderRepository } from '@core/llm-provider/repositories/llm-provider.repository';
import { LlmProviderRegistry } from '@core/llm-provider/services/llm-provider-registry.service';

@Injectable()
export class LlmProviderService {
  constructor(
    private readonly llmProviderRepository: LlmProviderRepository,
    private readonly tenantService: TenantService,
    private readonly registry: LlmProviderRegistry,
  ) {}

  async create(dto: CreateLlmProviderDto): Promise<LlmProvider> {
    const tenant = dto.tenantId
      ? await this.tenantService.requireTenant(dto.tenantId)
      : null;
    const provider = this.llmProviderRepository.create({
      name: dto.name,
      kind: dto.kind,
      baseUrl: dto.baseUrl ?? null,
      apiKey: dto.apiKey ?? null,
      defaultModel: dto.defaultModel ?? null,
      embeddingModel: dto.embeddingModel ?? null,
      isActive: dto.isActive ?? true,
      tenant,
    });

    const savedProvider = await this.llmProviderRepository.save(provider);
    this.registry.reload();

    return savedProvider;
  }

  async list(): Promise<LlmProvider[]> {
    return this.llmProviderRepository.findAll({
      orderBy: { id: 'DESC' },
    });
  }

  reloadRegistry(): { reloaded: true } {
    this.registry.reload();
    return { reloaded: true };
  }
}
