// import * as validator from 'class-validator';

import { PipeTransform, BadRequestException } from '@nestjs/common';

export class ParseIncludePipe implements PipeTransform {
  private readonly relations: string[] = [];
  private readonly outputType: 'array' | 'string' = 'array';
  private readonly separator: string = ',';

  constructor(options: {
    relations: string[];
    outputType?: 'array' | 'string';
    separator?: string;
  }) {
    this.relations = options.relations;

    if (options.outputType) this.outputType = options.outputType;
    if (options.separator) this.separator = options.separator;
  }

  parseAndValidate(value: any) {
    if (typeof value !== 'string')
      throw new BadRequestException('Given item must be a string.');

    return value;
  }

  transform(value: any) {
    if (value === undefined) return;

    const allowEverything =
      this.relations.length === 1 && this.relations[0] === '*';

    const includeArray = value.split(this.separator);

    if (!allowEverything) {
      for (const include of includeArray) {
        if (!this.relations.includes(include)) {
          throw new BadRequestException(`"${include}" is not authorized.`);
        }
      }
    }

    if (this.outputType === 'array') return includeArray;
    else return value;
  }
}
