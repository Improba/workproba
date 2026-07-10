import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { LlmProvider } from '@core/llm-provider/entities/llm-provider.entity';

@BaseCustomRepository(LlmProvider)
export class LlmProviderRepository extends BaseRepository<LlmProvider> {
  async findActiveForTenant(
    tenantId?: number | null,
  ): Promise<LlmProvider | null> {
    const tenantProvider = tenantId
      ? await this.findOne({ tenant: tenantId, isActive: true })
      : null;

    if (tenantProvider) {
      return tenantProvider;
    }

    return this.findOne({ tenant: null, isActive: true });
  }
}
