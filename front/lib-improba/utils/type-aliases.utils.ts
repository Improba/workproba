/**
 * Any object with unknown type of values
 */
// This could be ideal but... it does not work Record<string, unknown> | Record<string, unknown>[]
export type UnknownValues = any;

export type Primitive =
  | string
  | number
  | bigint
  | boolean
  | symbol
  | null
  | undefined;

export type CommonPrimitives = string | number | boolean;

/**
 * extract type of an item in an array, if it is an array
 * ```ts
 * T extends (infer U)[]
 * ```
 * can be read as
 * ```ts
 * T === U[]
 * ```
 */
export type ItemOfArray<Type> = Type extends (infer ItemType)[]
  ? ItemType
  : Type;

// to put in another file
export interface UpdateDto {
  id: number;
  [key: string]: unknown;
}
