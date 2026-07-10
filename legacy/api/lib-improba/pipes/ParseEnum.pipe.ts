import * as Validator from 'class-validator';

import { PipeTransform, BadRequestException } from '@nestjs/common';

export class ParseEnumPipe implements PipeTransform {
  private readonly type;

  constructor(options: any) {
    this.type = options;
  }

  private isInEnum(val: any, enumObj: any) {
    const enumKeys = Object.keys(enumObj);
    const result = enumKeys.find((key: string) => enumObj[key] === val);
    if (result) return true;
    else return false;
  }

  parseAndValidate(value: any) {
    if (!value) {
      throw new BadRequestException('Given item is undefined.');
    }

    switch (this.type) {
      case Number: {
        const parsedValue = +value;
        if (
          !Validator.isNumber(parsedValue, {
            allowNaN: false,
            allowInfinity: false,
          })
        )
          throw new BadRequestException('Given item must be a number.');

        return parsedValue;
      }
      default: {
        const parsedValue = value;

        if (!this.isInEnum(parsedValue, this.type))
          throw new BadRequestException('Given item must be in the enum.');

        return parsedValue;
      }
    }
  }

  transform(value: any) {
    if (value === undefined) return;
    return this.parseAndValidate(value);
  }
}
