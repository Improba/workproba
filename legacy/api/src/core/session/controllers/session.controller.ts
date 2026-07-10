import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { BaseController } from '@lib-improba/base/base.controller';
import { CreateMessageDto } from '@core/session/dtos/create-message.dto';
import { CreateSessionDto } from '@core/session/dtos/create-session.dto';
import { SessionService } from '@core/session/services/session.service';

@ApiTags('sessions')
@Controller()
export class SessionController extends BaseController {
  constructor(private readonly sessionService: SessionService) {
    super();
  }

  @Post('projects/:projectId/sessions')
  async createSession(
    @Param('projectId', ParseIntPipe) projectId: number,
    @Body() dto: CreateSessionDto,
  ) {
    return this.sessionService.createSession(projectId, dto);
  }

  @Get('projects/:projectId/sessions')
  async listSessions(@Param('projectId', ParseIntPipe) projectId: number) {
    return this.sessionService.listSessions(projectId);
  }

  @Post('sessions/:sessionId/messages/local')
  async createLocalMessage(
    @Param('sessionId', ParseIntPipe) sessionId: number,
    @Body() dto: CreateMessageDto,
  ) {
    return this.sessionService.createMessage(sessionId, dto);
  }

  @Get('sessions/:sessionId/messages')
  async listMessages(@Param('sessionId', ParseIntPipe) sessionId: number) {
    return this.sessionService.listMessages(sessionId);
  }
}
