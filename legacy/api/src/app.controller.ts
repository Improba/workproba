import { Controller, Get } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { AppService } from './app.service';

@ApiTags('app')
@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get()
  @ApiOperation({ summary: 'Page d\'accueil de l\'API', description: 'Retourne une page HTML avec le nom et la version de l\'application' })
  @ApiResponse({ status: 200, description: 'Page HTML retournée avec succès' })
  getHello(): string {
    return this.appService.getHello();
  }
}
