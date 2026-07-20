import { describe, expect, it } from 'vitest';
import {
  ANCHOR_VISIBLE_PX,
  SCROLL_PROMOTE_EPSILON,
  computeAnchorPeek,
  computeAnchorScrollTop,
  computeSpacerHeight,
  shouldPromoteAnchorToSticky,
} from '@composables/chatScroll';

describe('chatScroll helpers', () => {
  describe('computeAnchorPeek', () => {
    it('retourne 0 quand la taille est nulle ou négative', () => {
      expect(computeAnchorPeek(0)).toBe(0);
      expect(computeAnchorPeek(-10)).toBe(0);
    });

    it('retourne la taille quand elle est inférieure au peek', () => {
      expect(computeAnchorPeek(30)).toBe(30);
      expect(computeAnchorPeek(ANCHOR_VISIBLE_PX - 1)).toBe(
        ANCHOR_VISIBLE_PX - 1,
      );
    });

    it('plafonne au peek quand la taille dépasse', () => {
      expect(computeAnchorPeek(ANCHOR_VISIBLE_PX)).toBe(ANCHOR_VISIBLE_PX);
      expect(computeAnchorPeek(200)).toBe(ANCHOR_VISIBLE_PX);
    });

    it('respecte un peek personnalisé', () => {
      expect(computeAnchorPeek(80, 40)).toBe(40);
      expect(computeAnchorPeek(20, 40)).toBe(20);
    });
  });

  describe('computeAnchorScrollTop', () => {
    it('retourne itemOffset quand la taille est nulle', () => {
      expect(computeAnchorScrollTop(100, 0)).toBe(100);
    });

    it('ancre avec peek partiel pour un message court', () => {
      const size = 30;
      const offset = 200;
      expect(computeAnchorScrollTop(offset, size)).toBe(offset + size - size);
    });

    it('ancre avec peek fixe pour un message long', () => {
      const size = 120;
      const offset = 200;
      expect(computeAnchorScrollTop(offset, size)).toBe(
        offset + size - ANCHOR_VISIBLE_PX,
      );
    });

    it('ne retourne jamais une valeur négative', () => {
      expect(computeAnchorScrollTop(-50, 100)).toBe(0);
    });
  });

  describe('computeSpacerHeight', () => {
    it('retourne 0 pour un viewport trop petit', () => {
      expect(computeSpacerHeight(0)).toBe(0);
      expect(computeSpacerHeight(ANCHOR_VISIBLE_PX)).toBe(0);
      expect(computeSpacerHeight(ANCHOR_VISIBLE_PX - 1)).toBe(0);
    });

    it('soustrait le peek visible du viewport', () => {
      expect(computeSpacerHeight(500)).toBe(500 - ANCHOR_VISIBLE_PX);
    });

    it('respecte un peek personnalisé', () => {
      expect(computeSpacerHeight(300, 40)).toBe(260);
    });
  });

  describe('shouldPromoteAnchorToSticky', () => {
    const clientHeight = 400;

    it('retourne false quand le contenu ne remplit pas le viewport', () => {
      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 300,
          scrollTop: 0,
          clientHeight,
        }),
      ).toBe(false);
    });

    it('retourne true quand le contenu atteint le bas du viewport', () => {
      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 400,
          scrollTop: 0,
          clientHeight,
        }),
      ).toBe(true);
    });

    it('retourne true à la borne epsilon', () => {
      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 400 - SCROLL_PROMOTE_EPSILON,
          scrollTop: 0,
          clientHeight,
        }),
      ).toBe(true);
    });

    it('retourne false juste sous la borne epsilon', () => {
      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 400 - SCROLL_PROMOTE_EPSILON - 1,
          scrollTop: 0,
          clientHeight,
        }),
      ).toBe(false);
    });

    it('tient compte du scrollTop', () => {
      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 500,
          scrollTop: 100,
          clientHeight,
        }),
      ).toBe(true);

      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 450,
          scrollTop: 100,
          clientHeight,
        }),
      ).toBe(false);
    });

    it('accepte un epsilon personnalisé', () => {
      expect(
        shouldPromoteAnchorToSticky({
          contentEnd: 398,
          scrollTop: 0,
          clientHeight,
          epsilon: 5,
        }),
      ).toBe(true);
    });
  });
});
