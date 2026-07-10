export function isValidFileFormat(input: string) {
  return /^[a-zA-Z0-9_-]+$/.test(input) && input.length > 0;
}
