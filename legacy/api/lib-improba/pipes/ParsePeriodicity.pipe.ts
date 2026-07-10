import { Injectable, PipeTransform } from '@nestjs/common';
import { BadRequestException } from '@nestjs/common';

@Injectable()
export class ParsePeriodicity implements PipeTransform<string | undefined> {
  async transform(value?: string) {
    if (!value) return;

    const validPeriodicities = ['M', 'Ta', 'Tb', 'Tc'];

    if (!validPeriodicities.includes(value))
      throw new BadRequestException('Incorrect periodicity.');

    return value;
  }
}
