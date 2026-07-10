export function enumKeys<
  O extends Record<string, unknown>,
  K extends keyof O = keyof O,
>(obj: O): K[] {
  return Object.keys(obj).filter((k) => Number.isNaN(+k)) as K[];
}

export function enumValues<O extends Record<string, unknown>>(obj: O) {
  const keys = enumKeys(obj);
  const values = [];

  for (const key of keys) {
    values.push(obj[key]);
  }

  return values;
}
