import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Patch,
  Post,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { BaseController } from '@lib-improba/base/base.controller';
import { CreateTenantDto } from '@core/tenant/dtos/create-tenant.dto';
import { UpdateTenantDto } from '@core/tenant/dtos/update-tenant.dto';
import { TenantService } from '@core/tenant/services/tenant.service';

@ApiTags('tenants')
@Controller('tenants')
export class TenantController extends BaseController {
  constructor(private readonly tenantService: TenantService) {
    super();
  }

  @Post()
  async create(@Body() dto: CreateTenantDto) {
    return this.tenantService.createTenant(dto);
  }

  @Get()
  async list() {
    return this.tenantService.findAll();
  }

  @Get(':id')
  async findOne(@Param('id', ParseIntPipe) id: number) {
    return this.tenantService.requireTenant(id);
  }

  @Patch(':id')
  async update(
    @Param('id', ParseIntPipe) id: number,
    @Body() dto: UpdateTenantDto,
  ) {
    return this.tenantService.updateTenant(id, dto);
  }
}
