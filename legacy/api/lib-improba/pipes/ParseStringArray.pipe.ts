// import * as validator from 'class-validator';

import { PipeTransform, BadRequestException } from '@nestjs/common';

export class ParseStringArrayPipe implements PipeTransform {
  private readonly outputType: 'array' | 'string' = 'array';
  private readonly separator: string = ',';

  constructor(options: {
    outputType?: 'array' | 'string';
    separator?: string;
  }) {
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

    // const allowEverything =
    //   this.relations.length === 1 && this.relations[0] === '*';

    const stringArray = value.split(this.separator);

    // if (!allowEverything) {
    //   for (const include of stringArray) {
    //     if (!this.relations.includes(include)) {
    //       throw new BadRequestException(`"${include}" is not authorized.`);
    //     }
    //   }
    // }

    // for (let str in stringArray) {
    //   const s = [...str];
    //   if (s.length > 0) {
    //     if (s[0] === '*') s[0] = '%';

    //     const lastIndex = s.length - 1;
    //     if (s[lastIndex] === '*') s[lastIndex] = '%';
    //   }
    //   str = s.join();
    // }

    if (this.outputType === 'array') return stringArray;
    else return value;
  }
}
