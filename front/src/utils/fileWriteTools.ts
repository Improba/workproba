const FILE_WRITE_TOOL_NAMES = new Set([
  'write_docx',
  'write_xlsx',
  'write_pptx',
  'write_pdf',
  'generate_document',
  'edit',
]);

const OFFICE_WRITE_TOOL_NAMES = new Set([
  'write_docx',
  'write_xlsx',
  'write_pptx',
  'write_pdf',
]);

export function isFileWriteTool(toolName: string): boolean {
  return FILE_WRITE_TOOL_NAMES.has(toolName);
}

export function isOfficeWriteTool(toolName: string): boolean {
  return OFFICE_WRITE_TOOL_NAMES.has(toolName);
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

/** Indique si l'aperçu avant écriture est disponible pour cet outil. */
export function canPreviewFileWrite(
  toolName: string,
  args: Record<string, unknown> | undefined,
): boolean {
  if (!isFileWriteTool(toolName)) return false;
  if (!args || typeof args !== 'object') return false;
  if (isOfficeWriteTool(toolName)) {
    // write_pptx: exiger une liste slides (même vide → deck par défaut côté builder)
    if (toolName === 'write_pptx') {
      return Array.isArray(args.slides);
    }
    return true;
  }
  return extractProposedContent(args) !== null;
}

/** Chemin relatif proposé par un outil d'écriture fichier (path ou name). */
export function extractProposedPath(
  args: Record<string, unknown> | undefined,
): string | null {
  if (!args) return null;
  for (const key of ['path', 'name'] as const) {
    const value = args[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}
