// Write a custom nestjs pipe allowing an int or an undefined value
// The pipe should be named ParseIntOrUndefinedPipe

import { ArgumentMetadata, BadRequestException, Injectable, PipeTransform } from '@nestjs/common';

export class ParseIntOrUndefinedPipe implements PipeTransform {
  protected parseAndValidate(value: any, metadata: ArgumentMetadata): number | undefined {
    if (value === undefined) return value;
    const v = parseInt(value, 10);
    if (isNaN(v)) {
      throw new BadRequestException(`${metadata.data ?? '-'}: Given item must be a number.`);
    }

    return v;
  }

  public transform(value: string, metadata: ArgumentMetadata) {
    const parseDateValue = this.parseAndValidate(value, metadata);
    return parseDateValue;
  }
}