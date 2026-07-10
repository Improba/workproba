import { Body, Controller, Post } from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { BaseController } from '@lib-improba/base/base.controller';
import { IndexDocumentDto } from '@core/kb/dtos/index-document.dto';
import { SearchKbDto } from '@core/kb/dtos/search-kb.dto';
import { KbService } from '@core/kb/services/kb.service';

@ApiTags('knowledge-base')
@Controller('kb')
export class KbController extends BaseController {
  constructor(private readonly kbService: KbService) {
    super();
  }

  @Post('index')
  async index(@Body() dto: IndexDocumentDto) {
    return this.kbService.index(dto);
  }

  @Post('search')
  async search(@Body() dto: SearchKbDto) {
    return this.kbService.search(dto);
  }
}
