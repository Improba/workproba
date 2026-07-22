import { describe, expect, it } from 'vitest';
import {
  ANCHOR_CLAMP_PX,
  clampAnchorPeek,
  computeAnchorScrollTop,
  computeDynamicSpacer,
  messageHasAnchorableContent,
  messageHasThinking,
  scrollToItemOffsetForPeek,
  shouldPromoteAnchorToSticky,
  shouldSuspendAnchorForCollapsedThinking,
} from '@composables/chatScrollAnchor';

describe('chatScrollAnchor', () => {
  describe('clampAnchorPeek', () => {
    it('laisse les messages courts entièrement visibles', () => {
      expect(clampAnchorPeek(28)).toBe(28);
    });

    it('clamp les messages longs', () => {
      expect(clampAnchorPeek(400)).toBe(ANCHOR_CLAMP_PX);
    });

    it('retourne 0 pour taille invalide', () => {
      expect(clampAnchorPeek(0)).toBe(0);
      expect(clampAnchorPeek(-10)).toBe(0);
    });
  });

  describe('computeDynamicSpacer', () => {
    it('réserve quasi un viewport au début (réponse vide)', () => {
      const peek = 40;
      const viewport = 800;
      expect(
        computeDynamicSpacer({
          viewportHeight: viewport,
          anchorPeek: peek,
          responseHeight: 0,
        }),
      ).toBe(viewport - peek);
    });

    it('réduit la réserve à mesure que la réponse grandit', () => {
      expect(
        computeDynamicSpacer({
          viewportHeight: 800,
          anchorPeek: 96,
          responseHeight: 200,
        }),
      ).toBe(800 - 96 - 200);
    });

    it('atteint 0 quand la réponse remplit', () => {
      expect(
        computeDynamicSpacer({
          viewportHeight: 800,
          anchorPeek: 96,
          responseHeight: 704,
        }),
      ).toBe(0);
      expect(
        computeDynamicSpacer({
          viewportHeight: 800,
          anchorPeek: 96,
          responseHeight: 900,
        }),
      ).toBe(0);
    });
  });

  describe('shouldPromoteAnchorToSticky', () => {
    it('promote seulement spacer <= 0', () => {
      expect(shouldPromoteAnchorToSticky(1)).toBe(false);
      expect(shouldPromoteAnchorToSticky(0)).toBe(true);
      expect(shouldPromoteAnchorToSticky(-1)).toBe(true);
    });
  });

  describe('scrollToItemOffsetForPeek', () => {
    it('est 0 pour un message court (entièrement visible)', () => {
      expect(scrollToItemOffsetForPeek(40)).toBe(0);
    });

    it('décale d’un message long pour ne garder que le peek', () => {
      expect(scrollToItemOffsetForPeek(400)).toBe(400 - ANCHOR_CLAMP_PX);
    });

    it('reste cohérent avec computeAnchorScrollTop', () => {
      const userOffset = 12_000; // historique long
      const userSize = 250;
      const peek = clampAnchorPeek(userSize);
      const viaOffset = userOffset + scrollToItemOffsetForPeek(userSize);
      const viaScrollTop = computeAnchorScrollTop({
        userOffset,
        userSize,
        anchorPeek: peek,
      });
      expect(viaOffset).toBe(viaScrollTop);
    });
  });

  describe('promote behavior', () => {
    it('promouvoit quand la réponse remplit viewport - peek', () => {
      const viewport = 700;
      const peek = 96;
      const response = viewport - peek;
      const spacer = computeDynamicSpacer({
        viewportHeight: viewport,
        anchorPeek: peek,
        responseHeight: response,
      });
      expect(spacer).toBe(0);
      expect(shouldPromoteAnchorToSticky(spacer)).toBe(true);
    });

    it('reste en ancre tant que la réponse est courte', () => {
      const spacer = computeDynamicSpacer({
        viewportHeight: 700,
        anchorPeek: 40,
        responseHeight: 120,
      });
      expect(spacer).toBeGreaterThan(0);
      expect(shouldPromoteAnchorToSticky(spacer)).toBe(false);
    });
  });

  describe('collapsed thinking suspend', () => {
    it('détecte le contenu ancrable (texte / tool)', () => {
      expect(messageHasAnchorableContent({ content: 'hi' })).toBe(true);
      expect(messageHasAnchorableContent({ content: '  ' })).toBe(false);
      expect(
        messageHasAnchorableContent({
          content: '',
          parts: [{ type: 'tool_call' }],
        }),
      ).toBe(true);
      expect(
        messageHasAnchorableContent({
          content: '',
          parts: [{ type: 'thinking' }],
        }),
      ).toBe(false);
    });

    it('détecte la présence de thinking', () => {
      expect(messageHasThinking({ thinking: '' })).toBe(true);
      expect(messageHasThinking({ parts: [{ type: 'thinking' }] })).toBe(true);
      expect(messageHasThinking({ content: 'x' })).toBe(false);
    });

    it('suspend seulement thinking-only replié', () => {
      expect(
        shouldSuspendAnchorForCollapsedThinking({
          hasAnchorableContent: false,
          hasThinking: true,
          thinkingExpanded: false,
        }),
      ).toBe(true);
      expect(
        shouldSuspendAnchorForCollapsedThinking({
          hasAnchorableContent: false,
          hasThinking: true,
          thinkingExpanded: true,
        }),
      ).toBe(false);
      expect(
        shouldSuspendAnchorForCollapsedThinking({
          hasAnchorableContent: true,
          hasThinking: true,
          thinkingExpanded: false,
        }),
      ).toBe(false);
      expect(
        shouldSuspendAnchorForCollapsedThinking({
          hasAnchorableContent: false,
          hasThinking: false,
          thinkingExpanded: false,
        }),
      ).toBe(false);
    });
  });
});
