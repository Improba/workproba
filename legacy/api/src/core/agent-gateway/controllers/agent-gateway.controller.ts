import {
  Body,
  Controller,
  Header,
  Param,
  ParseIntPipe,
  Post,
} from '@nestjs/common';
import { ApiTags } from '@nestjs/swagger';
import { Observable } from 'rxjs';
import { BaseController } from '@lib-improba/base/base.controller';
import { AgentMessageDto } from '@core/agent-gateway/dtos/agent-message.dto';
import { AgentGatewayService } from '@core/agent-gateway/services/agent-gateway.service';

@ApiTags('agent-gateway')
@Controller('sessions')
export class AgentGatewayController extends BaseController {
  constructor(private readonly agentGatewayService: AgentGatewayService) {
    super();
  }

  /**
   * Flux SSE pass-through : les blocs events Python sont retransmis tels quels
   * au client (event: token | tool_call_start | tool_call_result | done | error).
   */
  @Post(':sessionId/messages')
  @Header('Content-Type', 'text/event-stream')
  @Header('Cache-Control', 'no-cache')
  @Header('Connection', 'keep-alive')
  streamMessage(
    @Param('sessionId', ParseIntPipe) sessionId: number,
    @Body() dto: AgentMessageDto,
  ): Observable<string> {
    return this.agentGatewayService.streamTurn(sessionId, dto);
  }
}
