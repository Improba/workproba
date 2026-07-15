import { describe, expect, it } from 'vitest';
import {
  canPreviewFileWrite,
  extractProposedContent,
  isOfficeWriteTool,
} from '@utils/fileWriteTools';

describe('fileWriteTools', () => {
  it('active le preview Office avec tool_args', () => {
    expect(
      canPreviewFileWrite('write_docx', {
        path: 'note.docx',
        paragraphs: ['Hello'],
      }),
    ).toBe(true);
    expect(extractProposedContent({ paragraphs: ['Hello'] })).toBeNull();
    expect(isOfficeWriteTool('write_docx')).toBe(true);
  });

  it('exige du contenu texte pour les outils non Office', () => {
    expect(canPreviewFileWrite('edit', { new_content: 'x' })).toBe(true);
    expect(canPreviewFileWrite('edit', { path: 'a.txt' })).toBe(false);
  });
});
