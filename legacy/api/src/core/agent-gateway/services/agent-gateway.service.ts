import { Readable } from 'node:stream';
import axios from 'axios';
import { Observable, Subscriber } from 'rxjs';
import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { AgentMessageDto } from '@core/agent-gateway/dtos/agent-message.dto';
import { KbService } from '@core/kb/services/kb.service';
import { MessageRoleEnum } from '@core/session/entities/message.entity';
import { SessionService } from '@core/session/services/session.service';

export interface AgentSseEvent {
  type: string;
  data: Record<string, unknown>;
}

/**
 * Pass-through SSE proxy vers le service Python "cœur IA".
 *
 * Le backend retransmet les blocs SSE Python tels quels au client
 * (event: token | tool_call_start | tool_call_result | done | error)
 * afin que le frontend parse le contrat SSE natif. En parallèle, il
 * accumule le contenu assistant pour persister le message final.
 *
 * Schéma V1 : Python n'a pas de credential DB, c'est NestJS qui persiste.
 */
@Injectable()
export class AgentGatewayService {
  constructor(
    private readonly configService: ConfigService,
    private readonly sessionService: SessionService,
    private readonly kbService: KbService,
  ) {}

  streamTurn(sessionId: number, dto: AgentMessageDto): Observable<string> {
    return new Observable((subscriber) => {
      void this.forwardTurn(sessionId, dto, subscriber);
    });
  }

  private async forwardTurn(
    sessionId: number,
    dto: AgentMessageDto,
    subscriber: Subscriber<string>,
  ): Promise<void> {
    try {
      const userMessage = await this.sessionService.createMessage(sessionId, {
        role: MessageRoleEnum.User,
        content: dto.content,
        parentId: dto.parentId,
        metadata: dto.metadata,
      });

      const context = await this.sessionService.getAgentContext(sessionId);
      const project = context.session.project;
      const tenant = project.tenant;
      const kbResults = await this.kbService.search({
        tenantId: tenant.id,
        projectId: project.id,
        query: dto.content,
        limit: 8,
      });

      const response = await axios.post<Readable>(
        `${this.getAgentServiceUrl()}/agent/turn`,
        {
          tenant_id: String(tenant.id),
          project_id: String(project.id),
          session_id: String(sessionId),
          message: dto.content,
          history: context.messages.map((message) => ({
            role: message.role,
            content: message.content,
          })),
          documents: kbResults.map((row) => ({
            id: String(row.documentId ?? row.id),
            name: row.documentId
              ? `document-${row.documentId}`
              : `chunk-${row.chunkIndex}`,
            metadata: {
              chunkIndex: row.chunkIndex,
              content: row.content,
              score: row.score,
            },
          })),
        },
        {
          headers: {
            Accept: 'text/event-stream',
            'X-Internal-Secret': this.getInternalSecret(),
          },
          responseType: 'stream',
        },
      );

      let assistantContent = '';
      let buffer = '';
      for await (const chunk of response.data) {
        buffer += chunk.toString();
        let sepIndex: number;
        while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
          const rawBlock = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);
          if (!rawBlock.trim()) continue;

          const parsed = this.parseSseBlock(rawBlock);
          if (parsed?.type === 'token') {
            const token =
              typeof parsed.data?.content === 'string'
                ? parsed.data.content
                : typeof parsed.data?.token === 'string'
                  ? parsed.data.token
                  : '';
            assistantContent += token;
          }

          subscriber.next(`${rawBlock}\n\n`);
        }
      }

      await this.sessionService.createMessage(sessionId, {
        role: MessageRoleEnum.Assistant,
        content: assistantContent,
        parentId: userMessage.id,
      });

      subscriber.complete();
    } catch (error) {
      subscriber.error(error);
    }
  }

  private parseSseBlock(rawBlock: string): AgentSseEvent | null {
    let type = 'message';
    const dataLines: string[] = [];
    for (const line of rawBlock.split('\n')) {
      if (line.startsWith('event:')) {
        type = line.slice('event:'.length).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trim());
      }
    }
    if (dataLines.length === 0) return null;
    try {
      return { type, data: JSON.parse(dataLines.join('\n')) };
    } catch {
      return { type, data: { raw: dataLines.join('\n') } };
    }
  }

  private getAgentServiceUrl(): string {
    return this.configService.get<string>(
      'AI_SERVICE_URL',
      'http://workproba-ai:8000',
    );
  }

  private getInternalSecret(): string {
    return this.configService.get<string>('AI_INTERNAL_SECRET', '');
  }
}
