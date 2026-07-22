/** Turn-anchor scroll helpers (état de l'art : question en haut + réserve pour la réponse). */

/** Hauteur max visible du tour user en ancre (≈ 6em). */
export const ANCHOR_CLAMP_PX = 96;

export type ChatScrollMode = 'anchor' | 'sticky' | 'detached';

/** Peek visible du message user ancré (messages courts entièrement visibles). */
export function clampAnchorPeek(
  userTurnHeight: number,
  clampMaxPx = ANCHOR_CLAMP_PX,
): number {
  if (userTurnHeight <= 0) return 0;
  return Math.min(userTurnHeight, clampMaxPx);
}

/**
 * Contenu digne d'ancrage (texte / outils / confirmations), hors raisonnement seul.
 * Le header ThinkingCard replié n'en fait pas partie.
 */
export function messageHasAnchorableContent(message: {
  content?: string | null;
  toolCalls?: readonly unknown[] | null;
  parts?: readonly { type: string; content?: string }[] | null;
  pendingConfirmation?: unknown;
  pendingPlan?: unknown;
}): boolean {
  if (message.content?.trim()) return true;
  if ((message.toolCalls?.length ?? 0) > 0) return true;
  if (message.pendingConfirmation || message.pendingPlan) return true;
  for (const part of message.parts ?? []) {
    if (part.type === 'tool_call') return true;
    if (part.type === 'text' && part.content?.trim()) return true;
  }
  return false;
}

/** Message assistant avec au moins un segment / champ thinking. */
export function messageHasThinking(message: {
  thinking?: string | null;
  parts?: readonly { type: string }[] | null;
}): boolean {
  if (message.thinking != null) return true;
  return (message.parts ?? []).some((part) => part.type === 'thinking');
}

/**
 * Phase thinking-only repliée : pas de contenu utile + raisonnement présent
 * mais non déplié. Dans ce cas le spacer turn-anchor réserverait un quasi
 * viewport vide sous le header (~60px) — on suspend l'ancre (sticky-bottom).
 */
export function shouldSuspendAnchorForCollapsedThinking(params: {
  hasAnchorableContent: boolean;
  hasThinking: boolean;
  thinkingExpanded: boolean;
}): boolean {
  if (params.hasAnchorableContent) return false;
  if (!params.hasThinking) return false;
  return !params.thinkingExpanded;
}

/**
 * Réserve sous le tour user pour laisser déplier la réponse.
 * Se réduit quand responseHeight grandit ; 0 quand la réponse remplit le viewport.
 */
export function computeDynamicSpacer(params: {
  viewportHeight: number;
  anchorPeek: number;
  responseHeight: number;
}): number {
  const { viewportHeight, anchorPeek, responseHeight } = params;
  if (viewportHeight <= 0) return 0;
  return Math.max(0, viewportHeight - anchorPeek - Math.max(0, responseHeight));
}

/** Promouvoir anchor → sticky quand la réserve a disparu. */
export function shouldPromoteAnchorToSticky(spacerHeight: number): boolean {
  return spacerHeight <= 0;
}

/**
 * scrollTop équivalent pour tests / doc.
 * Runtime : préférer `scrollToItemOffsetForPeek` + `scrollToItem(align:'start')`
 * (stabilise les mesures du virtual scroller sur historique long).
 */
export function computeAnchorScrollTop(params: {
  userOffset: number;
  userSize: number;
  anchorPeek: number;
}): number {
  const { userOffset, userSize, anchorPeek } = params;
  if (userSize <= 0) return Math.max(0, userOffset);
  const peek = clampAnchorPeek(userSize, Math.max(anchorPeek, 1));
  return Math.max(0, userOffset + userSize - peek);
}

/** Offset passé à scrollToItem(align:'start') pour afficher le peek clampé. */
export function scrollToItemOffsetForPeek(
  userSize: number,
  clampMaxPx = ANCHOR_CLAMP_PX,
): number {
  if (userSize <= 0) return 0;
  const peek = clampAnchorPeek(userSize, clampMaxPx);
  return Math.max(0, userSize - peek);
}
