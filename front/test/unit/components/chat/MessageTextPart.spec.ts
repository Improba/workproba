import { mount, flushPromises } from '@vue/test-utils';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import MessageTextPart, {
  defaultCodeHtml,
  sanitizeMarkdownHtml,
} from '@components/chat/MessageTextPart.vue';
import * as markdownRender from '@utils/markdownRender';

describe('MessageTextPart', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(markdownRender, 'preloadHighlighter').mockResolvedValue(undefined);
    vi.spyOn(markdownRender, 'highlightCodeBlocks').mockResolvedValue(undefined);
    vi.spyOn(markdownRender, 'bindCopyButtons').mockImplementation(() => undefined);
  });

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

  it('rend KaTeX dans les blocs stables pendant le streaming', async () => {
    const fullSpy = vi.spyOn(markdownRender, 'renderMarkdownFull');
    const plainSpy = vi.spyOn(markdownRender, 'renderMarkdownPlain');

    const wrapper = mount(MessageTextPart, {
      props: {
        content: '$$x = 1$$\n\nSuite',
        streaming: true,
      },
    });
    await flushPromises();

    expect(fullSpy).toHaveBeenCalled();
    const stableBlock = wrapper.find('[data-block-key="0"]');
    expect(stableBlock.exists()).toBe(true);
    expect(stableBlock.html()).toContain('katex');

    const tail = wrapper.find('.chat-message__md-block--tail');
    expect(tail.exists()).toBe(true);
    expect(plainSpy).toHaveBeenCalled();
    wrapper.unmount();
  });

  it('enrichit les blocs stables avec highlight après rendu', async () => {
    const highlightSpy = vi.spyOn(markdownRender, 'highlightCodeBlocks');
    const content = '```js\nconst x = 1\n```\n\nSuite';

    const wrapper = mount(MessageTextPart, {
      props: {
        content,
        streaming: true,
      },
    });
    await flushPromises();

    const stableBlocks = wrapper.findAll('[data-block-key]');
    expect(stableBlocks.length).toBe(1);
    expect(highlightSpy).toHaveBeenCalled();
    wrapper.unmount();
  });

  it('utilise le rendu plain pour la queue ouverte', async () => {
    const plainSpy = vi.spyOn(markdownRender, 'renderMarkdownPlain');
    const content = '$$x = 1$$\n\n```js\nconst x = 1\n';

    const wrapper = mount(MessageTextPart, {
      props: {
        content,
        streaming: true,
      },
    });
    await flushPromises();

    const tail = wrapper.find('.chat-message__md-block--tail');
    expect(tail.exists()).toBe(true);
    expect(tail.html()).not.toContain('katex');

    const tailCalls = plainSpy.mock.calls.map(([source]) => source);
    expect(tailCalls.some((source) => source.includes('```js'))).toBe(true);
    wrapper.unmount();
  });

  it('conserve les blocs stables à la fin du streaming sans basculer sur finalHtml', async () => {
    const content = 'Premier\n\nDeuxième';

    const wrapper = mount(MessageTextPart, {
      props: {
        content,
        streaming: true,
      },
    });
    await flushPromises();

    expect(wrapper.findAll('[data-block-key]').length).toBeGreaterThanOrEqual(1);

    await wrapper.setProps({ streaming: false });
    await flushPromises();

    const stableBlocks = wrapper.findAll('[data-block-key]');
    expect(stableBlocks.length).toBeGreaterThanOrEqual(2);
    expect(wrapper.find('.chat-message__md-block--tail').exists()).toBe(false);

    const markdownRoot = wrapper.find('.chat-message__markdown');
    const directChildren = markdownRoot.element.children;
    expect(directChildren.length).toBeGreaterThanOrEqual(2);
    for (const child of directChildren) {
      expect(child.classList.contains('chat-message__md-block')).toBe(true);
    }
    wrapper.unmount();
  });

  it('n’affiche pas le curseur si le contenu texte est vide', async () => {
    const wrapper = mount(MessageTextPart, {
      props: {
        content: '',
        streaming: true,
        showCursor: true,
      },
    });
    await flushPromises();
    expect(wrapper.find('[data-testid="chat-message-cursor"]').exists()).toBe(
      false,
    );
    wrapper.unmount();
  });

  it('colle le curseur en fin de queue de stream quand il y a du texte', async () => {
    const wrapper = mount(MessageTextPart, {
      props: {
        content: 'Salut',
        streaming: true,
        showCursor: true,
      },
    });
    await flushPromises();

    const cursor = wrapper.find('[data-testid="chat-message-cursor"]');
    expect(cursor.exists()).toBe(true);
    expect(cursor.element.parentElement?.classList.contains('chat-message__stream-tail')).toBe(
      true,
    );
    expect(
      wrapper.find('.chat-message__markdown').element.contains(cursor.element),
    ).toBe(true);
    wrapper.unmount();
  });
});
