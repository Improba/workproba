import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import katex from 'katex';
import { createHighlighter, type Highlighter } from 'shiki';

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
});

let linkSanitizeHookInstalled = false;

function installLinkSanitizeHook(): void {
  if (linkSanitizeHookInstalled) return;
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName !== 'A' || !node.hasAttribute('href')) return;
    const href = node.getAttribute('href') ?? '';
    if (/^(?:https?:|mailto:)/i.test(href)) {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
  });
  linkSanitizeHookInstalled = true;
}

function hardenExternalLinks(html: string): string {
  if (typeof DOMParser === 'undefined') return html;
  const doc = new DOMParser().parseFromString(html, 'text/html');
  doc.querySelectorAll('a[href]').forEach((anchor) => {
    const href = anchor.getAttribute('href') ?? '';
    if (/^(?:https?:|mailto:)/i.test(href)) {
      anchor.setAttribute('target', '_blank');
      anchor.setAttribute('rel', 'noopener noreferrer');
    }
  });
  return doc.body.innerHTML;
}

/** Sanitize le HTML markdown avant injection dans le DOM. */
export function sanitizeMarkdownHtml(html: string): string {
  installLinkSanitizeHook();
  const sanitized = DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
    ADD_ATTR: ['target', 'rel'],
  });
  return hardenExternalLinks(sanitized);
}

function escapeHtmlAttr(value: string): string {
  return md.utils.escapeHtml(value);
}

export function renderKatex(source: string): string {
  let output = source;

  output = output.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr: string) => {
    try {
      return katex.renderToString(expr.trim(), { displayMode: true });
    } catch {
      return `$$${expr}$$`;
    }
  });

  output = output.replace(/(?<!\$)\$([^$\n]+?)\$(?!\$)/g, (_, expr: string) => {
    try {
      return katex.renderToString(expr.trim(), { displayMode: false });
    } catch {
      return `$${expr}$`;
    }
  });

  return output;
}

export function defaultCodeHtml(code: string, lang: string): string {
  const escaped = md.utils.escapeHtml(code);
  const language = escapeHtmlAttr(lang || 'text');
  return `<div class="code-block" data-lang="${language}">
    <div class="code-block__toolbar">
      <span class="code-block__lang">${language}</span>
      <button type="button" class="code-block__copy"></button>
    </div>
    <pre class="code-block__pre"><code>${escaped}</code></pre>
  </div>`;
}

md.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx];
  const code = token.content;
  const lang = token.info.trim().split(/\s+/)[0] || 'text';
  return defaultCodeHtml(code, lang);
};

/** Rendu markdown sans KaTeX (streaming ou blocs stables). */
export function renderMarkdownPlain(source: string): string {
  if (!source) return '';
  return md.render(source);
}

/** Rendu markdown complet avec KaTeX (message terminé). */
export function renderMarkdownFull(source: string): string {
  if (!source) return '';
  return md.render(renderKatex(source));
}

let highlighter: Highlighter | null = null;
let highlighterPromise: Promise<Highlighter> | null = null;

async function getHighlighter(): Promise<Highlighter> {
  if (highlighter) return highlighter;
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ['github-light', 'github-dark'],
      langs: [
        'javascript',
        'typescript',
        'python',
        'json',
        'bash',
        'sql',
        'markdown',
        'html',
        'css',
        'text',
      ],
    });
  }
  highlighter = await highlighterPromise;
  return highlighter;
}

export async function highlightCodeBlocks(container: ParentNode | null): Promise<void> {
  if (!container) return;
  const blocks = container.querySelectorAll<HTMLElement>('.code-block');
  if (!blocks.length) return;

  const hl = await getHighlighter();
  const theme =
    document.documentElement.getAttribute('data-theme') === 'dark'
      ? 'github-dark'
      : 'github-light';

  blocks.forEach((block) => {
    const lang = block.dataset.lang || 'text';
    const pre = block.querySelector('code');
    if (!pre) return;
    const raw = pre.textContent ?? '';
    try {
      const html = hl.codeToHtml(raw, { lang, theme });
      const wrapper = document.createElement('div');
      wrapper.innerHTML = html;
      const highlighted = wrapper.querySelector('pre');
      if (highlighted) {
        pre.replaceWith(highlighted);
      }
    } catch {
      // Fallback texte brut
    }
  });
}

export function bindCopyButtons(
  root: ParentNode | null,
  labels: { copy: string; copied: string; failed: string },
): void {
  if (!root) return;
  root.querySelectorAll<HTMLElement>('.code-block').forEach((block) => {
    const btn = block.querySelector<HTMLButtonElement>('.code-block__copy');
    const code = block.querySelector('code');
    if (!btn || !code) return;

    btn.textContent = labels.copy;

    btn.onclick = async () => {
      const text = code.textContent ?? '';
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = labels.copied;
        setTimeout(() => {
          btn.textContent = labels.copy;
        }, 1500);
      } catch {
        btn.textContent = labels.failed;
        setTimeout(() => {
          btn.textContent = labels.copy;
        }, 1500);
      }
    };
  });
}
