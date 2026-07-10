import * as Validator from 'class-validator';

import { PipeTransform, BadRequestException } from '@nestjs/common';

export class ParseEnumArrayPipe implements PipeTransform {
  private readonly type;
  private readonly seperator: string;

  constructor(options: any) {
    this.type = options.type;
    this.seperator = options.separator;
  }

  parseAndValidate(value: any) {
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
        if (!Validator.isIn(parsedValue, this.type))
          throw new BadRequestException('Given item must be in the enum.');

        return parsedValue;
      }
    }
  }

  transform(value: any) {
    if (!value) return [];

    let items: any[];
    try {
      items = value.split(this.seperator);
    } catch (error) {
      throw new BadRequestException('Given input is not parsable.');
    }

    return items.map((item) => {
      return this.parseAndValidate(item);
    });
  }
}
