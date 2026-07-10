import { IsBoolean, IsOptional, IsString, MaxLength } from 'class-validator';

export class CreateTenantDto {
  @IsString()
  @MaxLength(200)
  name!: string;

  @IsString()
  @MaxLength(120)
  slug!: string;

  @IsOptional()
  @IsBoolean()
  isActive?: boolean;
}
