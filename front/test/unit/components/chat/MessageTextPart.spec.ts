import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import MessageTextPart, {
  defaultCodeHtml,
  sanitizeMarkdownHtml,
} from '@components/chat/MessageTextPart.vue';

describe('MessageTextPart', () => {
  it('supprime les liens javascript: du HTML rendu', async () => {
    const wrapper = mount(MessageTextPart, {
      props: {
        content: '[x](javascript:alert(1))',
        streaming: false,
      },
    });
    await flushPromises();

    const links = wrapper.element.querySelectorAll('a');
    for (const link of links) {
      const href = link.getAttribute('href') ?? '';
      expect(href.startsWith('javascript:')).toBe(false);
    }
    wrapper.unmount();
  });

  it('conserve un lien http normal avec attributs de sécurité', async () => {
    const wrapper = mount(MessageTextPart, {
      props: {
        content: '[site](https://example.com)',
        streaming: false,
      },
    });
    await flushPromises();

    const link = wrapper.element.querySelector('a');
    expect(link?.getAttribute('href')).toBe('https://example.com');
    expect(link?.getAttribute('target')).toBe('_blank');
    expect(link?.getAttribute('rel')).toBe('noopener noreferrer');
    wrapper.unmount();
  });

  it('échappe data-lang quand la langue contient un guillemet', () => {
    const html = defaultCodeHtml('const x = 1', 'ts" onclick="alert(1)');
    expect(html).toContain('data-lang="ts&quot; onclick=&quot;alert(1)"');
    expect(html).not.toContain('data-lang="ts" onclick');
  });

  it('sanitizeMarkdownHtml bloque les href javascript:', () => {
    const sanitized = sanitizeMarkdownHtml(
      '<a href="javascript:alert(1)">bad</a><a href="https://ok.test">good</a>',
    );
    expect(sanitized).not.toMatch(/href="javascript:/);
    expect(sanitized).toContain('href="https://ok.test"');
  });

  it('rend les blocs stables séparément pendant le streaming', async () => {
    const wrapper = mount(MessageTextPart, {
      props: {
        content: 'Premier paragraphe\n\nDeuxième',
        streaming: true,
      },
    });
    await flushPromises();

    const blocks = wrapper.findAll('.chat-message__md-block');
    expect(blocks.length).toBeGreaterThanOrEqual(2);
    wrapper.unmount();
  });
});
