import { Injectable, NotFoundException } from '@nestjs/common';
import { WorkspaceService } from '@core/workspace/services/workspace.service';
import { CreateMessageDto } from '@core/session/dtos/create-message.dto';
import { CreateSessionDto } from '@core/session/dtos/create-session.dto';
import { Message, MessageRoleEnum } from '@core/session/entities/message.entity';
import { Session } from '@core/session/entities/session.entity';
import { MessageRepository } from '@core/session/repositories/message.repository';
import { SessionRepository } from '@core/session/repositories/session.repository';

export interface AgentSessionContext {
  session: Session;
  messages: Array<{
    id: number;
    parentId: number | null;
    role: MessageRoleEnum;
    content: string;
  }>;
}

@Injectable()
export class SessionService {
  constructor(
    private readonly sessionRepository: SessionRepository,
    private readonly messageRepository: MessageRepository,
    private readonly workspaceService: WorkspaceService,
  ) {}

  async createSession(
    projectId: number,
    dto: CreateSessionDto,
  ): Promise<Session> {
    const project = await this.workspaceService.requireProject(projectId);
    const session = this.sessionRepository.create({
      project,
      title: dto.title ?? null,
      metadata: dto.metadata ?? null,
    });

    return this.sessionRepository.save(session);
  }

  async listSessions(projectId: number): Promise<Session[]> {
    await this.workspaceService.requireProject(projectId);
    return this.sessionRepository.findByProject(projectId);
  }

  async requireSession(sessionId: number): Promise<Session> {
    const session = await this.sessionRepository.findOneById(sessionId, {
      populate: ['project', 'project.tenant'],
    });
    if (!session) {
      throw new NotFoundException(`Session ${sessionId} not found`);
    }

    return session;
  }

  async createMessage(
    sessionId: number,
    dto: CreateMessageDto,
  ): Promise<Message> {
    const session = await this.requireSession(sessionId);
    const message = this.messageRepository.create({
      session,
      role: dto.role,
      content: dto.content,
      parentId: dto.parentId ?? null,
      metadata: dto.metadata ?? null,
    });

    return this.messageRepository.save(message);
  }

  async listMessages(sessionId: number): Promise<Message[]> {
    await this.requireSession(sessionId);
    return this.messageRepository.findBySession(sessionId);
  }

  async getAgentContext(sessionId: number): Promise<AgentSessionContext> {
    const session = await this.requireSession(sessionId);
    const messages = await this.messageRepository.findBySession(sessionId);

    return {
      session,
      messages: messages.map((message) => ({
        id: message.id,
        parentId: message.parentId ?? null,
        role: message.role,
        content: message.content,
      })),
    };
  }
}
