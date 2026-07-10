import {
  Body,
  Controller,
  DefaultValuePipe,
  Get,
  Post,
  Param,
  Patch,
  Query,
  Req,
  UseGuards,
  HttpException,
  HttpStatus,
  NotFoundException,
  InternalServerErrorException,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiBody,
} from '@nestjs/swagger';

import { JwtAuthGuard } from '@users/guards/jwt-auth.guard';
import { UserRolesGuard } from '@users/guards/user-roles.guard';
import { UserRoleEnum } from '@users/entities/user.entity';
import { BaseController } from '@lib-improba/base/base.controller';

import { UserService } from '../services/user.service';
import { Roles } from '../decorators/roles';

// import { UserPatchDto } from '../entities/user.entity';
import { User } from '../entities/user.entity';
import {
  IPaginationOptions,
  IPaginationOutput,
} from '@lib-improba/base/base.repository';
import { ParseEnumArrayPipe, ParseIncludePipe } from '@lib-improba/pipes';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';
import { IsBoolean, IsNotEmpty, IsNumber, IsOptional, IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class UserUpdateCurrentDto {
  @ApiProperty({ required: false, description: 'Prénom de l\'utilisateur', example: 'John' })
  @IsOptional()
  @IsString()
  firstname?: string;

  @ApiProperty({ required: false, description: 'Nom de l\'utilisateur', example: 'Doe' })
  @IsOptional()
  @IsString()
  lastname?: string;

  @ApiProperty({ required: false, description: 'Préférence pour le thème sombre', example: true })
  @IsOptional()
  @IsBoolean()
  preferDarkTheme?: boolean;

  @ApiProperty({ required: false, description: 'Indique si une réinitialisation de mot de passe est en cours', example: false })
  @IsOptional()
  @IsBoolean()
  resetPasswordOngoing?: boolean;
}

export class UserUpdateDto extends UserUpdateCurrentDto {
  @ApiProperty({ description: 'ID de l\'utilisateur', example: 1 })
  @IsNotEmpty()
  @IsNumber()
  id!: number;
}

@ApiTags('users')
@Controller('users')
export class UserController extends BaseController {
  constructor(
    private readonly service: UserService,
    private readonly userJwtService: UserJwtService,
  ) {
    super();
  }

  @Get('current')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.User)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Récupérer l\'utilisateur connecté', description: 'Retourne les informations de l\'utilisateur actuellement authentifié' })
  @ApiResponse({ status: 200, description: 'Utilisateur trouvé', type: User })
  @ApiResponse({ status: 404, description: 'Utilisateur non trouvé' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  async get(@Req() req: any): Promise<User> {
    const userId = req.user.id;
    const user = await this.service.findOneById(userId);
    if (!user) {
      throw new NotFoundException('User does not exist');
    }
    return user;
  }

  @Patch('current')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.User)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Mettre à jour l\'utilisateur connecté', description: 'Met à jour les informations de l\'utilisateur actuellement authentifié' })
  @ApiBody({ type: UserUpdateCurrentDto })
  @ApiResponse({ status: 200, description: 'Utilisateur mis à jour avec succès', type: User })
  @ApiResponse({ status: 500, description: 'Erreur lors de la mise à jour' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  async update(
    @Req() req: any,
    @Body() body: UserUpdateCurrentDto,
  ): Promise<User> {
    const userId = req.user.id;
    const user = await this.service.update({
      ...body,
      id: userId,
    });
    if (!user) {
      throw new InternalServerErrorException('User could not be updated');
    }

    return user;
  }
}
