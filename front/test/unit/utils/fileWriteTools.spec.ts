import { describe, expect, it } from 'vitest';
import {
  canPreviewFileWrite,
  extractProposedContent,
  extractProposedPath,
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
    expect(
      canPreviewFileWrite('write_pptx', {
        path: 'deck.pptx',
        slides: [{ layout: 'title', title: 'Hello' }],
      }),
    ).toBe(true);
    expect(canPreviewFileWrite('write_pptx', { path: 'deck.pptx' })).toBe(false);
    expect(canPreviewFileWrite('write_pptx', { path: 'deck.pptx', slides: [] })).toBe(
      true,
    );
    expect(extractProposedContent({ paragraphs: ['Hello'] })).toBeNull();
    expect(isOfficeWriteTool('write_docx')).toBe(true);
    expect(isOfficeWriteTool('write_pptx')).toBe(true);
  });

  it('extrait le chemin proposé depuis path ou name', () => {
    expect(extractProposedPath({ path: 'deck/pitch.pptx' })).toBe(
      'deck/pitch.pptx',
    );
    expect(extractProposedPath({ name: 'note.md' })).toBe('note.md');
    expect(extractProposedPath({ paragraphs: ['x'] })).toBeNull();
  });

  it('exige du contenu texte pour les outils non Office', () => {
    expect(canPreviewFileWrite('edit', { new_content: 'x' })).toBe(true);
    expect(canPreviewFileWrite('edit', { path: 'a.txt' })).toBe(false);
  });
});
