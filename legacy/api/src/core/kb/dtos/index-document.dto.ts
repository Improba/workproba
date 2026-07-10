import { IsInt, IsOptional, IsString, Min } from 'class-validator';

export class IndexDocumentDto {
  @IsInt()
  tenantId!: number;

  @IsInt()
  projectId!: number;

  @IsOptional()
  @IsInt()
  documentId?: number;

  @IsInt()
  @Min(0)
  chunkIndex!: number;

  @IsString()
  content!: string;
}
