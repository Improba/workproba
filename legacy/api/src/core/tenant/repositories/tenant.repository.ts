import { BaseRepository } from '@lib-improba/base/base.repository';
import { BaseCustomRepository } from '@lib-improba/decorators';
import { Tenant } from '@core/tenant/entities/tenant.entity';

@BaseCustomRepository(Tenant)
export class TenantRepository extends BaseRepository<Tenant> {
  async findActiveBySlug(slug: string): Promise<Tenant | null> {
    return this.findOne({ slug, isActive: true });
  }
}
