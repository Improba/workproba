import { describe, expect, it } from 'vitest';
import {
  parseBrowserHighlight,
  scaleHighlightStyle,
} from '@utils/browserHighlight';

describe('browserHighlight', () => {
  it('parseBrowserHighlight extrait ref, bbox et viewport', () => {
    const highlight = parseBrowserHighlight({
      action_ref: 'e42',
      action_bbox: { x: 10, y: 20, width: 100, height: 32 },
      viewport: { width: 1280, height: 720 },
    });
    expect(highlight?.ref).toBe('e42');
    expect(highlight?.bbox.width).toBe(100);
  });

  it('scaleHighlightStyle adapte au ratio affiché', () => {
    const style = scaleHighlightStyle(
      {
        ref: 'e1',
        bbox: { x: 128, y: 72, width: 256, height: 36 },
        viewport: { width: 1280, height: 720 },
      },
      640,
    );
    expect(style?.left).toBe('64px');
    expect(style?.top).toBe('36px');
    expect(style?.width).toBe('128px');
  });

  it('parseBrowserHighlight retourne null si bbox absente', () => {
    expect(
      parseBrowserHighlight({
        action_ref: 'e1',
        viewport: { width: 1280, height: 720 },
      }),
    ).toBeNull();
  });
});
