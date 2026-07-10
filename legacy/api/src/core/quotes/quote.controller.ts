import { Controller, Get, UseGuards } from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
} from '@nestjs/swagger';
import { BaseController } from '@lib-improba/base/base.controller';
import { JwtAuthGuard } from '@users/guards/jwt-auth.guard';
import { UserRolesGuard } from '@users/guards/user-roles.guard';
import { UserRoleEnum } from '@users/entities/user.entity';
import { Roles } from '@users/decorators/roles';
import { QuoteService } from './quote.service';
import { QuoteResponseDto } from './dto/quote-response.dto';

@ApiTags('quotes')
@Controller('quotes')
export class QuoteController extends BaseController {
  constructor(private readonly quoteService: QuoteService) {
    super();
  }

  @Get('random')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.User)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({
    summary: 'Générer une phrase aléatoire',
    description: 'Retourne une phrase générée complètement aléatoirement par le backend',
  })
  @ApiResponse({
    status: 200,
    description: 'Phrase générée avec succès',
    type: QuoteResponseDto,
  })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé' })
  getRandomQuote(): QuoteResponseDto {
    return this.quoteService.generateRandomQuote();
  }
}

