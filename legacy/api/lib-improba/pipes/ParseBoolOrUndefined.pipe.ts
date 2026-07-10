import { PipeTransform, BadRequestException, Injectable } from '@nestjs/common';

@Injectable()
export class ParseBoolOrUndefinedPipe implements PipeTransform {
  transform(value: any) {
    if (value !== undefined && value !== 'false' && value !== 'true')
      throw new BadRequestException('Given value is not bool or undefined.');

    if (value === 'false') return false;
    else if (value === 'true') return true;

    return undefined;
  }
}
