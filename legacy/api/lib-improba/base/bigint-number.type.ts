import { Type, Platform, TransformContext } from '@mikro-orm/core';

/**
 * Persist JS numbers as SQL bigint (string) and parse them back into numbers.
 * WARNING: you’ll lose precision above 2^53-1 (Number.MAX_SAFE_INTEGER).
 * But this a very very big number, so it's very unlikely to happen.
 * 
 * The class contains a check to throw an error if the number is too big for the js Number.MAX_SAFE_INTEGER.
 * This is to avoid losing precision.
 * */
export class BigIntNumberType extends Type<number | null, string | number | bigint | null> {
  override convertToDatabaseValue(
    value: number | null,
    platform: Platform,
    context?: TransformContext,
  ): string | null {
    if (value == null) return null;
    if (value > Number.MAX_SAFE_INTEGER) {
      throw new Error('Value is too large to be represented as a number');
    }
    return value.toString();
  }

  override convertToJSValue(
    value: string | number | bigint | null,
    platform: Platform,
  ): number | null {
    if (value == null) return null;

    let v: number;
    if (typeof value === 'number') v = value;
    else if (typeof value === 'bigint') v = Number(value);
    else v = Number.parseInt(value, 10);

    if (v > Number.MAX_SAFE_INTEGER) {
      throw new Error('Value is too large to be represented as a number');
    }
    return v;
  }

  override getColumnType(): string {
    return 'bigint';
  }

  // aide le diff interne
  override compareAsType() {
    return 'number' as const;
  }
} 