import { PipeTransform, BadRequestException, Injectable, ArgumentMetadata } from '@nestjs/common';

export class ParseStringOrUndefinedPipe implements PipeTransform {
  protected parseAndValidate(value: any, metadata: ArgumentMetadata & {
    choices?: string[];
  }): string | undefined {
    if (value === undefined) return value;

    if (typeof value !== 'string') {
      throw new BadRequestException(`${metadata.data ?? '-'}: Given item must be a string.`);
    }

    if (metadata.choices && !metadata.choices.includes(value)) {
      throw new BadRequestException(`${metadata.data ?? '-'}: Given item is not allowed.`);
    }
    
    return value;
  }
  
  transform(value: any, metadata: ArgumentMetadata & {
    choices?: string[];
  }) {
    const parsedValue = this.parseAndValidate(value, metadata);

    return parsedValue;
  }
}
