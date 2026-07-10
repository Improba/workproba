<template>
  <div class="chat-message__markdown" ref="markdownRoot" v-html="renderedHtml" />
  <span
    v-if="streaming && showCursor"
    class="chat-message__cursor"
    aria-hidden="true"
  />
</template>

<script lang="ts">
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import katex from 'katex';
import { createHighlighter, type Highlighter } from 'shiki';

// Singletons partagés par toutes les instances : on évite de recréer un parser
// markdown-it et un highlighter shiki (lourd) par segment de message.
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

function escapeHtmlAttr(value: string): string {
  return md.utils.escapeHtml(value);
}

let highlighter: Highlighter | null = null;
let highlighterPromise: Promise<Highlighter> | null = null;

function renderKatex(source: string): string {
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
      <button type="button" class="code-block__copy">Copier</button>
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

async function highlightCodeBlocks(container: ParentNode | null): Promise<void> {
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
      // Keep plain text fallback
    }
  });
}

function bindCopyButtons(root: ParentNode | null): void {
  if (!root) return;
  root.querySelectorAll<HTMLElement>('.code-block').forEach((block) => {
    const btn = block.querySelector<HTMLButtonElement>('.code-block__copy');
    const code = block.querySelector('code');
    if (!btn || !code) return;

    btn.onclick = async () => {
      const text = code.textContent ?? '';
      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = 'Copié';
        setTimeout(() => {
          btn.textContent = 'Copier';
        }, 1500);
      } catch {
        btn.textContent = 'Échec';
      }
    };
  });
}
</script>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useThrottleFn } from '@vueuse/core';
import 'katex/dist/katex.min.css';

const props = withDefaults(
  defineProps<{
    content: string;
    streaming?: boolean;
    showCursor?: boolean;
  }>(),
  { streaming: false, showCursor: false },
);

const renderedHtml = ref('');
const markdownRoot = ref<HTMLElement | null>(null);

async function updateRender(): Promise<void> {
  // Pendant le streaming : markdown seul (on skip KaTeX, coûteux et qui
  // clignote sur du math incomplet). Le rendu final applique KaTeX, puis
  // le watch renderedHtml pose boutons + highlighting.
  const rawHtml = props.streaming
    ? md.render(props.content)
    : md.render(renderKatex(props.content));
  renderedHtml.value = sanitizeMarkdownHtml(rawHtml);
}

const throttledUpdate = useThrottleFn(updateRender, 80);

watch(
  () => props.content,
  () => {
    if (props.streaming) {
      void throttledUpdate();
    } else {
      void updateRender();
    }
  },
  { immediate: true },
);

watch(renderedHtml, async () => {
  await Promise.resolve();
  // Aucune chirurgie DOM pendant le streaming : on rebindera boutons et
  // highlighting une fois le rendu final posé.
  if (props.streaming) return;
  bindCopyButtons(markdownRoot.value);
  await highlightCodeBlocks(markdownRoot.value);
});
</script>

<style scoped lang="scss">
.chat-message__markdown {
  :deep(p) {
    margin: 0 0 0.65rem;
  }

  :deep(p:last-child) {
    margin-bottom: 0;
  }

  :deep(a) {
    color: var(--text-link);
    text-decoration: underline;
  }

  :deep(ul),
  :deep(ol) {
    margin: 0.35rem 0 0.65rem 1.25rem;
  }

  :deep(.code-block) {
    margin: 0.65rem 0;
    border-radius: 10px;
    border: 1px solid var(--wp-border);
    overflow: hidden;
    background: var(--wp-surface-2);
  }

  :deep(.code-block__toolbar) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.35rem 0.65rem;
    background: var(--wp-surface-3);
    border-bottom: 1px solid var(--wp-border);
  }

  :deep(.code-block__lang) {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--wp-text-muted);
  }

  :deep(.code-block__copy) {
    border: none;
    background: transparent;
    color: var(--text-link);
    font-size: 0.75rem;
    cursor: pointer;
    padding: 0.15rem 0.35rem;
    border-radius: 6px;

    &:hover {
      background: var(--primary-lowest);
    }
  }

  :deep(pre) {
    margin: 0;
    padding: 0.75rem;
    overflow-x: auto;
    font-size: 0.82rem;
    line-height: 1.45;
  }
}

.chat-message__cursor {
  display: inline-block;
  width: 0.55rem;
  height: 1rem;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--primary);
  border-radius: 2px;
  animation: chat-cursor-blink 1s step-end infinite;
}

@keyframes chat-cursor-blink {
  50% {
    opacity: 0;
  }
}
</style>
