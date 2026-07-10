// import * as validator from 'class-validator';

import { PipeTransform, BadRequestException, ArgumentMetadata } from '@nestjs/common';

export class ParseFilterPipe implements PipeTransform {
  // constructor(options: any) {}
  constructor() {}

  parseAndValidate(value: any, metadata: ArgumentMetadata) {
    if (typeof value !== 'string')
      throw new BadRequestException(`${metadata.data ?? '-'}: Given item must be a string.`);

    return value;
  }

  transform(value: any, metadata: ArgumentMetadata) {
    if (value === undefined) return;

    const parsedValue = [...this.parseAndValidate(value, metadata)];

    if (parsedValue.length > 0) {
      if (parsedValue[0] === '*') parsedValue[0] = '%';

      const lastIndex = parsedValue.length - 1;
      if (parsedValue[lastIndex] === '*') parsedValue[lastIndex] = '%';
    }

    return parsedValue.join('');
  }
}
