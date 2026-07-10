function process(number: number, type: 'floor' | 'round' | 'ceil'): number {
  if (type === 'floor') return Math.floor(number);
  else if (type === 'ceil') return Math.ceil(number);
  else return Math.round(number);
}

export function formatNumber(
  number: number,
  options: {
    decimals: number;
    type: 'floor' | 'round' | 'ceil';
  } = { decimals: 0, type: 'round' }
): number {
  if (typeof number !== 'number') return number;
  const decimal = Math.pow(10, options.decimals);
  return process(number * decimal, options.type) / decimal;
}
