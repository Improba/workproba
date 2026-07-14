const FILE_WRITE_TOOL_NAMES = new Set([
  'write_docx',
  'write_xlsx',
  'write_pdf',
  'generate_document',
  'edit',
]);

export function isFileWriteTool(toolName: string): boolean {
  return FILE_WRITE_TOOL_NAMES.has(toolName);
}

/** Extrait le contenu proposé depuis les arguments d'un outil d'écriture fichier. */
export function extractProposedContent(
  args: Record<string, unknown> | undefined,
): string | null {
  if (!args) return null;
  const candidates = [
    args.proposed_content,
    args.content,
    args.content_markdown,
    args.new_content,
    args.text,
    args.body,
  ];
  for (const value of candidates) {
    if (typeof value === 'string' && value.length > 0) return value;
  }
  return null;
}
