import { createParamDecorator, ExecutionContext } from "@nestjs/common";
import { Populate, QueryOrder } from '@mikro-orm/core';
import { Transform, Type } from 'class-transformer';
import { IsEnum, IsNumber, IsOptional, IsString, Min } from 'class-validator';
import { ParseFilterPipe, ParseIntOrUndefinedPipe, ParseStringOrUndefinedPipe } from "lib-improba/pipes";

export const PaginationQueries = createParamDecorator(
  async (data: any, ctx: ExecutionContext) => {
    const parseIntOrUndefinedPipe = new ParseIntOrUndefinedPipe();
    const parseStringOrUndefinedPipe = new ParseStringOrUndefinedPipe();
    const parseFilterPipe = new ParseFilterPipe();
    
    const limit = parseIntOrUndefinedPipe.transform('limit', {
      type: 'query',
      metatype: Number,
      data: 'limit',
    });

    const offset = parseIntOrUndefinedPipe.transform('offset', {
      type: 'query',
      metatype: Number,
      data: 'offset',
    });

    const orderBy = parseStringOrUndefinedPipe.transform('orderBy', {
      type: 'query',
      metatype: String,
      data: 'orderBy',
    });

    const order = parseStringOrUndefinedPipe.transform('order', {
      type: 'query',
      metatype: String,
      data: 'order',
      choices: ['ASC', 'DESC'],
    });

    const q = parseFilterPipe.transform('q', {
      type: 'query',
      metatype: String,
      data: 'q',
    });

    return {
      limit: limit || 10,
      offset: offset || 0,
      orderBy: orderBy || 'id',
      order: order || 'DESC',
      q,
    }
    
  },
);

export class PaginationDTO<T> {
  @IsOptional()
  @IsNumber()
  @Min(1)
  @Type(() => Number)
  limit: number = 10;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Type(() => Number)
  offset: number = 0;

  @IsOptional()
  @IsString()
  orderBy?: keyof T;

  @IsOptional()
  @IsEnum(QueryOrder)
  order: QueryOrder = QueryOrder.ASC;

  @IsOptional()
  @IsString()
  q?: string;

  @IsOptional()
  @Transform(({ value }) => {
    if (!value) return undefined;
    if (Array.isArray(value)) return value;
    return typeof value === 'string' ? value.split(',').map((s) => s.trim()) : value;
  })
  populate?: Populate<T>;
}