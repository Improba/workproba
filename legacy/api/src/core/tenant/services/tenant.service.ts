import { Injectable, NotFoundException } from '@nestjs/common';
import { BaseService } from '@lib-improba/base/base.service';
import { Tenant } from '@core/tenant/entities/tenant.entity';
import { TenantRepository } from '@core/tenant/repositories/tenant.repository';
import { CreateTenantDto } from '@core/tenant/dtos/create-tenant.dto';
import { UpdateTenantDto } from '@core/tenant/dtos/update-tenant.dto';

@Injectable()
export class TenantService extends BaseService<Tenant, TenantRepository> {
  constructor(private readonly tenantRepository: TenantRepository) {
    super(tenantRepository);
  }

  async createTenant(dto: CreateTenantDto): Promise<Tenant> {
    const tenant = this.tenantRepository.create({
      ...dto,
      isActive: dto.isActive ?? true,
    });

    return this.tenantRepository.save(tenant);
  }

  async updateTenant(id: number, dto: UpdateTenantDto): Promise<Tenant> {
    const tenant = await this.tenantRepository.update(id, dto);
    return tenant;
  }

  async requireTenant(id: number): Promise<Tenant> {
    const tenant = await this.tenantRepository.findOneById(id);
    if (!tenant) {
      throw new NotFoundException(`Tenant ${id} not found`);
    }

    return tenant;
  }

  async findActiveBySlug(slug: string): Promise<Tenant | null> {
    return this.tenantRepository.findActiveBySlug(slug);
  }
}
