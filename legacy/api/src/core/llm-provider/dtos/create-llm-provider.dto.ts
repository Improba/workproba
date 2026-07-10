import {
  IsBoolean,
  IsEnum,
  IsInt,
  IsOptional,
  IsString,
  MaxLength,
} from 'class-validator';
import { LlmProviderKindEnum } from '@core/llm-provider/entities/llm-provider.entity';

export class CreateLlmProviderDto {
  @IsString()
  @MaxLength(120)
  name!: string;

  @IsEnum(LlmProviderKindEnum)
  kind!: LlmProviderKindEnum;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  baseUrl?: string;

  @IsOptional()
  @IsString()
  @MaxLength(500)
  apiKey?: string;

  @IsOptional()
  @IsString()
  @MaxLength(200)
  defaultModel?: string;

  @IsOptional()
  @IsString()
  @MaxLength(200)
  embeddingModel?: string;

  @IsOptional()
  @IsBoolean()
  isActive?: boolean;

  @IsOptional()
  @IsInt()
  tenantId?: number;
}
