import { IsInt, IsObject, IsOptional, IsString } from 'class-validator';

export class AgentMessageDto {
  @IsString()
  content!: string;

  @IsOptional()
  @IsInt()
  parentId?: number;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, unknown>;
}
