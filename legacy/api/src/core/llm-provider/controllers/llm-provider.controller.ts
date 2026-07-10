import { Body, Controller, Get, Post } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { BaseController } from '@lib-improba/base/base.controller';
import { CreateLlmProviderDto } from '@core/llm-provider/dtos/create-llm-provider.dto';
import { LlmProviderService } from '@core/llm-provider/services/llm-provider.service';

@ApiTags('llm-providers')
@Controller('llm-providers')
export class LlmProviderController extends BaseController {
  constructor(private readonly llmProviderService: LlmProviderService) {
    super();
  }

  @Post()
  async create(@Body() dto: CreateLlmProviderDto) {
    return this.llmProviderService.create(dto);
  }

  @Get()
  async list() {
    return this.llmProviderService.list();
  }

  @Post('reload')
  reload() {
    return this.llmProviderService.reloadRegistry();
  }
}
