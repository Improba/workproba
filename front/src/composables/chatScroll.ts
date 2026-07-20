export const ANCHOR_VISIBLE_PX = 52;
export const SCROLL_PROMOTE_EPSILON = 2;

export function computeAnchorPeek(
  itemSize: number,
  anchorVisiblePx = ANCHOR_VISIBLE_PX,
): number {
  if (itemSize <= 0) return 0;
  return Math.min(itemSize, anchorVisiblePx);
}

export function computeAnchorScrollTop(
  itemOffset: number,
  itemSize: number,
  anchorVisiblePx = ANCHOR_VISIBLE_PX,
): number {
  const peek = computeAnchorPeek(itemSize, anchorVisiblePx);
  return Math.max(0, itemOffset + itemSize - peek);
}

export function computeSpacerHeight(
  viewportHeight: number,
  anchorVisiblePx = ANCHOR_VISIBLE_PX,
): number {
  return Math.max(0, viewportHeight - anchorVisiblePx);
}

export function shouldPromoteAnchorToSticky(params: {
  contentEnd: number;
  scrollTop: number;
  clientHeight: number;
  epsilon?: number;
}): boolean {
  const {
    contentEnd,
    scrollTop,
    clientHeight,
    epsilon = SCROLL_PROMOTE_EPSILON,
  } = params;
  return contentEnd >= scrollTop + clientHeight - epsilon;
}
