import { IsObject, IsOptional, IsString, MaxLength } from 'class-validator';

export class CreateSessionDto {
  @IsOptional()
  @IsString()
  @MaxLength(255)
  title?: string;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, unknown>;
}
