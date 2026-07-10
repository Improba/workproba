import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  LlmProvider as LlmProviderClient,
  LlmProviderRuntimeConfig,
} from '@core/llm-provider/interfaces/llm-provider.interface';
import {
  LlmProvider as LlmProviderEntity,
  LlmProviderKindEnum,
} from '@core/llm-provider/entities/llm-provider.entity';
import { LlmProviderRepository } from '@core/llm-provider/repositories/llm-provider.repository';
import { MistralProvider } from '@core/llm-provider/providers/mistral.provider';
import { OpenAICompatProvider } from '@core/llm-provider/providers/openai-compat.provider';

@Injectable()
export class LlmProviderRegistry {
  private readonly cache = new Map<string, LlmProviderClient>();

  constructor(
    private readonly configService: ConfigService,
    private readonly llmProviderRepository: LlmProviderRepository,
  ) {}

  async resolve(tenantId?: number | null): Promise<LlmProviderClient> {
    const cacheKey = tenantId ? `tenant:${tenantId}` : 'global';
    const cachedProvider = this.cache.get(cacheKey);
    if (cachedProvider) {
      return cachedProvider;
    }

    const providerConfig =
      await this.llmProviderRepository.findActiveForTenant(tenantId);
    const provider = this.buildProvider(providerConfig);
    this.cache.set(cacheKey, provider);

    return provider;
  }

  reload(): void {
    this.cache.clear();
  }

  private buildProvider(
    providerConfig: LlmProviderEntity | null,
  ): LlmProviderClient {
    const kind =
      providerConfig?.kind ??
      this.configService.get<LlmProviderKindEnum>(
        'LLM_PROVIDER_KIND',
        LlmProviderKindEnum.OpenAICompatible,
      );
    const runtimeConfig: LlmProviderRuntimeConfig = {
      baseUrl:
        providerConfig?.baseUrl ??
        this.configService.get<string>('LLM_PROVIDER_BASE_URL'),
      apiKey:
        providerConfig?.apiKey ??
        this.configService.get<string>('LLM_PROVIDER_API_KEY'),
      defaultModel:
        providerConfig?.defaultModel ??
        this.configService.get<string>('LLM_PROVIDER_DEFAULT_MODEL'),
      embeddingModel:
        providerConfig?.embeddingModel ??
        this.configService.get<string>('LLM_PROVIDER_EMBEDDING_MODEL'),
    };

    if (kind === LlmProviderKindEnum.Mistral) {
      return new MistralProvider(runtimeConfig);
    }

    return new OpenAICompatProvider(runtimeConfig);
  }
}
