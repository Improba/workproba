import { IsEnum, IsInt, IsObject, IsOptional, IsString } from 'class-validator';
import { MessageRoleEnum } from '@core/session/entities/message.entity';

export class CreateMessageDto {
  @IsEnum(MessageRoleEnum)
  role!: MessageRoleEnum;

  @IsString()
  content!: string;

  @IsOptional()
  @IsInt()
  parentId?: number;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, unknown>;
}
