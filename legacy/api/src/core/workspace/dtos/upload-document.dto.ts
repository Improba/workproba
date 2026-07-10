import { IsObject, IsOptional, IsString, MaxLength } from 'class-validator';

export class UploadDocumentDto {
  @IsOptional()
  @IsString()
  @MaxLength(255)
  filename?: string;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  storagePath?: string;

  @IsOptional()
  @IsObject()
  metadata?: Record<string, unknown>;
}
