export interface BrowserViewport {
  width: number;
  height: number;
}

export interface BrowserHighlightBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface BrowserHighlightState {
  ref: string;
  bbox: BrowserHighlightBBox;
  viewport: BrowserViewport;
}

export function parseBrowserViewport(raw: unknown): BrowserViewport | null {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;
  const width = data.width;
  const height = data.height;
  if (typeof width !== 'number' || typeof height !== 'number') return null;
  if (width <= 0 || height <= 0) return null;
  return { width, height };
}

export function parseBrowserHighlightBBox(raw: unknown): BrowserHighlightBBox | null {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;
  const x = data.x;
  const y = data.y;
  const width = data.width;
  const height = data.height;
  if (
    typeof x !== 'number'
    || typeof y !== 'number'
    || typeof width !== 'number'
    || typeof height !== 'number'
  ) {
    return null;
  }
  if (width <= 0 || height <= 0) return null;
  return { x, y, width, height };
}

export function parseBrowserHighlight(
  data: Record<string, unknown>,
): BrowserHighlightState | null {
  const ref = data.action_ref;
  const bbox = parseBrowserHighlightBBox(data.action_bbox);
  const viewport = parseBrowserViewport(data.viewport);
  if (typeof ref !== 'string' || !ref || !bbox || !viewport) return null;
  return { ref, bbox, viewport };
}

/** Coordonnées CSS pour un overlay absolu sur l'image affichée. */
export function scaleHighlightStyle(
  highlight: BrowserHighlightState,
  displayWidth: number,
): Record<string, string> | null {
  if (displayWidth <= 0) return null;
  const scale = displayWidth / highlight.viewport.width;
  return {
    left: `${highlight.bbox.x * scale}px`,
    top: `${highlight.bbox.y * scale}px`,
    width: `${highlight.bbox.width * scale}px`,
    height: `${highlight.bbox.height * scale}px`,
  };
}
