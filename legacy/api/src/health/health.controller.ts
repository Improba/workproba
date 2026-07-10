import { Controller, Get } from '@nestjs/common';
import {
  HealthCheck,
  HealthCheckService,
  MikroOrmHealthIndicator,
} from '@nestjs/terminus';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';

@ApiTags('health')
@Controller('health')
export class HealthController {
  constructor(
    private readonly health: HealthCheckService,
    private readonly db: MikroOrmHealthIndicator,
  ) {}

  /** Utilisé par le healthcheck Docker (DB uniquement). */
  @Get()
  @HealthCheck()
  @ApiOperation({ summary: 'Health check (Docker)' })
  @ApiResponse({ status: 200, description: 'API et base de données disponibles' })
  @ApiResponse({ status: 503, description: 'Service indisponible' })
  check() {
    return this.health.check([() => this.db.pingCheck('database')]);
  }
}
