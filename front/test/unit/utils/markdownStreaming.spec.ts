import { describe, expect, it } from 'vitest';
import { splitMarkdownForStreaming } from '@utils/markdownStreaming';

describe('splitMarkdownForStreaming', () => {
  it('renvoie une queue vide pour un contenu vide', () => {
    expect(splitMarkdownForStreaming('')).toEqual({
      completeBlocks: [],
      tail: '',
    });
  });

  it('met tout en queue si aucun bloc complet', () => {
    expect(splitMarkdownForStreaming('Ligne unique')).toEqual({
      completeBlocks: [],
      tail: 'Ligne unique',
    });
  });

  it('sépare les paragraphes complets de la queue', () => {
    expect(splitMarkdownForStreaming('Premier\n\nDeuxième')).toEqual({
      completeBlocks: ['Premier'],
      tail: 'Deuxième',
    });
  });

  it('conserve une fence non fermée entièrement dans la queue', () => {
    const content = 'Intro\n\n```js\nconst x = 1\n';
    expect(splitMarkdownForStreaming(content)).toEqual({
      completeBlocks: ['Intro'],
      tail: '```js\nconst x = 1\n',
    });
  });

  it('finalise un bloc fence avant la queue', () => {
    const content = '```js\ncode\n```\n\nSuite';
    expect(splitMarkdownForStreaming(content)).toEqual({
      completeBlocks: ['```js\ncode\n```'],
      tail: 'Suite',
    });
  });

  it('accepte plusieurs blocs complets', () => {
    const content = 'A\n\nB\n\nC';
    expect(splitMarkdownForStreaming(content)).toEqual({
      completeBlocks: ['A', 'B'],
      tail: 'C',
    });
  });
});
