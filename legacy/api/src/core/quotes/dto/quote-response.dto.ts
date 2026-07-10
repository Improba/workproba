import { ApiProperty } from '@nestjs/swagger';

export class QuoteResponseDto {
  @ApiProperty({ description: 'Phrase générée aléatoirement', example: 'Les étoiles dansent avec les nuages dans un ciel infini' })
  quote!: string;
}

