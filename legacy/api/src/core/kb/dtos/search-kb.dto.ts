import { IsInt, IsOptional, IsString, Max, Min } from 'class-validator';

export class SearchKbDto {
  @IsInt()
  tenantId!: number;

  @IsInt()
  projectId!: number;

  @IsString()
  query!: string;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(50)
  limit?: number;
}
