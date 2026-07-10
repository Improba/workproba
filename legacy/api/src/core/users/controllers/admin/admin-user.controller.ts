import {
  Controller,
  Get,
  HttpStatus,
  HttpException,
  Post,
  Body,
  UseGuards,
  ClassSerializerInterceptor,
  UseInterceptors,
  Param,
  SerializeOptions,
  Query,
  DefaultValuePipe,
  Patch,
  Delete,
  NotFoundException,
  ValidationPipe,
  ExecutionContext,
  createParamDecorator,
  // Req,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiBody,
  ApiParam,
} from '@nestjs/swagger';

import { UserRolesGuard } from '../..//guards/user-roles.guard';
import { JwtAuthGuard } from '../../guards/jwt-auth.guard';
import { BaseController } from '@lib-improba/base/base.controller';
import { Roles } from '../../decorators/roles';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { ParseEnumArrayPipe } from '@lib-improba/pipes/ParseEnumArray.pipe';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { ParseFilterPipe } from '@lib-improba/pipes/ParseFilter.pipe';
import {
  IPaginationOutput,
} from '@lib-improba/base/base.repository';

import { UserService } from '../../services/user.service';
import { UserJwtService } from '@lib-improba/modules/auth-jwt/services/user-jwt.service';
import {
  ISearchQueryParams,
  SearchQueryParams,
} from '@lib-improba/decorators';
import { UserUpdateDto } from '../user.controller';
import { IsEnum, IsNotEmpty, IsNumber, IsOptional, IsString, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';
import { UserJwtCreateDto } from '@lib-improba/modules/auth-jwt/controllers/auth-jwt.controller';
import { ApiProperty } from '@nestjs/swagger';
import { PaginationDTO } from '@lib-improba/dtos';
import { User, UserRoleEnum } from '../../entities/user.entity';

export class PaginateUserDTO extends PaginationDTO<User> {
  @IsOptional()
  @IsEnum(UserRoleEnum)
  role?: UserRoleEnum;
}

export class UserCreateForAdminDto {
  @ApiProperty({ required: false, description: 'Prénom de l\'utilisateur', example: 'John' })
  @IsOptional()
  @IsString()
  firstname?: string;

  @ApiProperty({ required: false, description: 'Nom de l\'utilisateur', example: 'Doe' })
  @IsOptional()
  @IsString()
  lastname?: string;

  @ApiProperty({ description: 'Rôles de l\'utilisateur', enum: UserRoleEnum, isArray: true, example: [UserRoleEnum.User] })
  @IsNotEmpty()
  @IsEnum(UserRoleEnum, { each: true })
  roles!: UserRoleEnum[];

  @ApiProperty({ required: false, description: 'Informations d\'authentification JWT', type: UserJwtCreateDto })
  @IsOptional()
  @ValidateNested({ each: true })
  @Type(() => UserJwtCreateDto)
  userJwt?: UserJwtCreateDto;
}

export class AdminUserUpdateDto extends UserUpdateDto {
  @ApiProperty({ required: false, description: 'Rôles de l\'utilisateur', enum: UserRoleEnum, isArray: true, example: [UserRoleEnum.User] })
  @IsOptional()
  @IsEnum(UserRoleEnum, { each: true })
  roles?: UserRoleEnum[];
}

@ApiTags('admin')
@Controller('users-admin')
export class AdminUserController extends BaseController {
  constructor(
    private readonly service: UserService,
    private readonly userJwtService: UserJwtService,
  ) {
    super();
  }

  @Get()
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Liste tous les utilisateurs', description: 'Retourne la liste complète de tous les utilisateurs (réservé aux administrateurs)' })
  @ApiResponse({ status: 200, description: 'Liste des utilisateurs', type: [User] })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async getAll(): Promise<User[]> {
    const users = await this.service.getAll();
    return users;
  }

  @Get('paginate')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Pagination des utilisateurs', description: 'Retourne une liste paginée des utilisateurs avec filtres et tri' })
  @ApiResponse({ status: 200, description: 'Liste paginée des utilisateurs' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async paginate(
    @Query() dto: PaginateUserDTO,
  ): Promise<IPaginationOutput<any>> {
    const results = await this.service.paginate(dto);
    return results;
  }

  @Get(':id')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Récupérer un utilisateur par ID', description: 'Retourne les informations d\'un utilisateur spécifique' })
  @ApiParam({ name: 'id', type: 'number', description: 'ID de l\'utilisateur' })
  @ApiResponse({ status: 200, description: 'Utilisateur trouvé', type: User })
  @ApiResponse({ status: 404, description: 'Utilisateur non trouvé' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async getOne(@Param('id') id: number): Promise<Partial<User>> {
    const user = await this.service.findOneById(id);
    if (!user) {
      throw new NotFoundException(`User with id ${id} not found`);
    }
    return user;
  }

  /*@Patch('resetPassword/:id')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  async resetPassword(@Param('id') id: number): Promise<{
    id: number;
    tempPassword: string;
  }> {
    // TODO: Implement this
  }*/

  @Post()
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Créer un nouvel utilisateur', description: 'Crée un nouvel utilisateur avec les rôles et informations fournis' })
  @ApiBody({ type: UserCreateForAdminDto })
  @ApiResponse({ status: 201, description: 'Utilisateur créé avec succès', type: User })
  @ApiResponse({ status: 400, description: 'Échec de la création (ex: username déjà utilisé)' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async create(@Body() body: UserCreateForAdminDto): Promise<Partial<User>> {
    try {
      if (body.userJwt?.username) {
        const usernameExists = await this.userJwtService.findByUsername(
          body.userJwt.username,
        );
        if (usernameExists) {
          throw new HttpException(
            'Un utilisateur existe déjà avec ce nom, essayez autre chose',
            HttpStatus.BAD_REQUEST,
          );
        }
      }
      return await this.service.create(body);
    } catch (err) {
      console.error(err);
      throw new HttpException('Creation impossible', HttpStatus.BAD_REQUEST);
    }
  }

  @Patch()
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Mettre à jour un utilisateur', description: 'Met à jour les informations d\'un utilisateur existant' })
  @ApiBody({ type: AdminUserUpdateDto })
  @ApiResponse({ status: 200, description: 'Utilisateur mis à jour avec succès', type: User })
  @ApiResponse({ status: 400, description: 'Échec de la mise à jour' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async update(
    @Body() body: AdminUserUpdateDto
  ): Promise<User | undefined> {
    try {
      return await this.service.updateAdmin(body);

    } catch (err) {
      console.error(err);
      throw new HttpException('Creation impossible', HttpStatus.BAD_REQUEST);
    }
  }

  @Patch('current')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Mettre à jour l\'utilisateur connecté (admin)', description: 'Met à jour les informations de l\'administrateur actuellement authentifié' })
  @ApiBody({ type: AdminUserUpdateDto })
  @ApiResponse({ status: 200, description: 'Utilisateur mis à jour avec succès', type: User })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async updateCurrent(
    @Body() body: AdminUserUpdateDto,
  ): Promise<User> {
    const userUpdated = await this.service.updateAdmin(body);
    return <User>userUpdated;
  }

  @Delete(':id')
  @UseGuards(JwtAuthGuard, UserRolesGuard)
  @Roles(UserRoleEnum.Admin)
  @ApiBearerAuth('JWT-auth')
  @ApiOperation({ summary: 'Supprimer un utilisateur', description: 'Supprime un utilisateur par son ID (soft delete)' })
  @ApiParam({ name: 'id', type: 'number', description: 'ID de l\'utilisateur à supprimer' })
  @ApiResponse({ status: 200, description: 'Utilisateur supprimé avec succès', type: User })
  @ApiResponse({ status: 404, description: 'Utilisateur non trouvé' })
  @ApiResponse({ status: 401, description: 'Non authentifié' })
  @ApiResponse({ status: 403, description: 'Accès refusé - droits administrateur requis' })
  async remove(@Param('id') id: number): Promise<User> {
    const user = await this.service.delete(id);
    if (!user) {
      throw new NotFoundException(`User with id ${id} not found`);
    }
    return user;
  }
}
