import { describe, expect, it } from 'vitest';
import { extractWebSearchCitations } from '@utils/webSearchCitations';
import type { ChatMessage } from '#types';

function assistantMessage(toolCalls: ChatMessage['toolCalls']): ChatMessage {
  return {
    id: 'a1',
    role: 'assistant',
    content: 'Réponse.',
    toolCalls,
    createdAt: '2026-01-01T00:00:00.000Z',
  };
}

describe('extractWebSearchCitations', () => {
  it('extrait title, url et snippet depuis web_search results', () => {
    const citations = extractWebSearchCitations(
      assistantMessage([
        {
          id: 'tc-1',
          name: 'web_search',
          status: 'success',
          args: { query: 'météo Paris' },
          result: {
            query: 'météo Paris',
            count: 1,
            results: [
              {
                title: 'Météo France',
                url: 'https://meteofrance.com/',
                snippet: 'Prévisions pour Paris.',
              },
            ],
          },
        },
      ]),
    );

    expect(citations).toEqual([
      {
        title: 'Météo France',
        url: 'https://meteofrance.com/',
        snippet: 'Prévisions pour Paris.',
      },
    ]);
  });

  it('déduplique par URL et fusionne citations + results', () => {
    const citations = extractWebSearchCitations(
      assistantMessage([
        {
          id: 'tc-1',
          name: 'web_search',
          status: 'success',
          args: {},
          result: {
            results: [{ title: 'A', url: 'https://a.test/', snippet: '' }],
            citations: [{ title: 'A', url: 'https://a.test/' }],
          },
        },
        {
          id: 'tc-2',
          name: 'web_search',
          status: 'success',
          args: {},
          result: {
            results: [{ title: 'B', url: 'https://b.test/', snippet: 'B snippet' }],
          },
        },
      ]),
    );

    expect(citations.map((c) => c.url)).toEqual(['https://a.test/', 'https://b.test/']);
  });

  it('ignore les appels en erreur ou sans résultat', () => {
    expect(
      extractWebSearchCitations(
        assistantMessage([
          { id: 'tc-err', name: 'web_search', status: 'error', args: {}, result: {} },
          { id: 'tc-other', name: 'search_kb', status: 'success', args: {}, result: {} },
        ]),
      ),
    ).toEqual([]);
  });
});
