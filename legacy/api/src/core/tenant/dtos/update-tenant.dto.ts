import { PartialType } from '@nestjs/mapped-types';
import { CreateTenantDto } from '@core/tenant/dtos/create-tenant.dto';

export class UpdateTenantDto extends PartialType(CreateTenantDto) {}
