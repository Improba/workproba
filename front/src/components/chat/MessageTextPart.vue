<template>
  <div ref="markdownRoot" class="chat-message__markdown">
    <template v-if="props.streaming || blocksActive">
      <div
        v-for="block in stableBlocks"
        :key="`stable-${block.key}`"
        class="chat-message__md-block"
        :data-block-key="block.key"
        v-html="block.html"
      />
      <span
        v-if="props.streaming && (tailHtml || visibleCursor)"
        class="chat-message__stream-tail"
      >
        <span
          v-if="tailHtml"
          class="chat-message__md-block chat-message__md-block--tail"
          v-html="tailHtml"
        />
        <span
          v-if="visibleCursor"
          class="chat-message__cursor"
          data-testid="chat-message-cursor"
          aria-hidden="true"
        />
      </span>
    </template>
    <div v-else v-html="finalHtml" />
  </div>
</template>

<script lang="ts">
export { defaultCodeHtml, sanitizeMarkdownHtml } from '@utils/markdownRender';
</script>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useThrottleFn } from '@vueuse/core';
import {
  bindCopyButtons,
  highlightCodeBlocks,
  preloadHighlighter,
  renderMarkdownFull,
  renderMarkdownPlain,
  sanitizeMarkdownHtml,
} from '@utils/markdownRender';
import { splitMarkdownForStreaming } from '@utils/markdownStreaming';
import 'katex/dist/katex.min.css';

const props = withDefaults(
  defineProps<{
    content: string;
    streaming?: boolean;
    showCursor?: boolean;
  }>(),
  { streaming: false, showCursor: false },
);

const { t } = useI18n();

/** Curseur seulement s'il y a du texte (indépendant du raisonnement replié/déplié). */
const visibleCursor = computed(
  () =>
    Boolean(props.streaming) &&
    Boolean(props.showCursor) &&
    props.content.trim().length > 0,
);

interface RenderBlock {
  key: number;
  html: string;
}

const stableBlocks = ref<RenderBlock[]>([]);
const tailHtml = ref('');
const finalHtml = ref('');
const blockSources = ref<string[]>([]);
const blocksActive = ref(false);
const enrichedKeys = ref(new Set<number>());
const markdownRoot = ref<HTMLElement | null>(null);

const copyLabels = computed(() => ({
  copy: t('chat.codeCopy'),
  copied: t('chat.codeCopied'),
  failed: t('chat.codeCopyFailed'),
}));

function buildStableBlocks(sources: string[]): RenderBlock[] {
  const nextStable: RenderBlock[] = [];
  const nextEnriched = new Set<number>();
  for (let i = 0; i < sources.length; i++) {
    const source = sources[i];
    const cached =
      blockSources.value[i] === source ? stableBlocks.value[i] : null;
    if (cached) {
      nextStable.push(cached);
      if (enrichedKeys.value.has(i)) nextEnriched.add(i);
    } else {
      nextStable.push({
        key: i,
        html: sanitizeMarkdownHtml(renderMarkdownFull(source)),
      });
    }
  }
  enrichedKeys.value = nextEnriched;
  return nextStable;
}

function pruneEnrichedKeys(validKeys: Set<number>): void {
  enrichedKeys.value = new Set(
    [...enrichedKeys.value].filter((key) => validKeys.has(key)),
  );
}

async function enrichNewStableBlocks(): Promise<void> {
  const root = markdownRoot.value;
  if (!root) return;

  const blockEls = root.querySelectorAll<HTMLElement>(
    '.chat-message__md-block[data-block-key]',
  );
  for (const el of blockEls) {
    const key = Number(el.dataset.blockKey);
    if (Number.isNaN(key) || enrichedKeys.value.has(key)) continue;
    await highlightCodeBlocks(el);
    bindCopyButtons(el, copyLabels.value);
    enrichedKeys.value = new Set([...enrichedKeys.value, key]);
  }
}

function rebuildStreaming(content: string): void {
  const { completeBlocks, tail } = splitMarkdownForStreaming(content);
  stableBlocks.value = buildStableBlocks(completeBlocks);
  blockSources.value = completeBlocks;
  tailHtml.value = tail
    ? sanitizeMarkdownHtml(renderMarkdownPlain(tail))
    : '';
  void nextTick(() => enrichNewStableBlocks());
}

function rebuildBlocksActive(content: string): void {
  const { completeBlocks, tail } = splitMarkdownForStreaming(content);
  const allSources = [...completeBlocks];
  if (tail.trim()) {
    allSources.push(tail);
  }
  stableBlocks.value = buildStableBlocks(allSources);
  blockSources.value = allSources;
  tailHtml.value = '';
  pruneEnrichedKeys(new Set(stableBlocks.value.map((block) => block.key)));
  void nextTick(() => enrichNewStableBlocks());
}

function finalizeStreaming(content: string): void {
  const { completeBlocks, tail } = splitMarkdownForStreaming(content);
  const allSources = [...completeBlocks];
  if (tail.trim()) {
    allSources.push(tail);
  }
  stableBlocks.value = buildStableBlocks(allSources);
  blockSources.value = allSources;
  tailHtml.value = '';
  blocksActive.value = true;
  pruneEnrichedKeys(new Set(stableBlocks.value.map((block) => block.key)));
  void nextTick(() => enrichNewStableBlocks());
}

function rebuildFinal(content: string): void {
  stableBlocks.value = [];
  blockSources.value = [];
  tailHtml.value = '';
  blocksActive.value = false;
  enrichedKeys.value.clear();
  finalHtml.value = sanitizeMarkdownHtml(renderMarkdownFull(content));
}

const throttledStreamingUpdate = useThrottleFn(() => {
  if (!props.streaming) return;
  rebuildStreaming(props.content);
}, 80, true);

watch(
  () => props.streaming,
  (streaming, wasStreaming) => {
    if (wasStreaming && !streaming) {
      finalizeStreaming(props.content);
    } else if (!wasStreaming && streaming) {
      blocksActive.value = false;
      enrichedKeys.value.clear();
      rebuildStreaming(props.content);
    }
  },
  { flush: 'sync' },
);

watch(
  () => props.content,
  () => {
    if (props.streaming) {
      void throttledStreamingUpdate();
      return;
    }
    if (blocksActive.value) {
      rebuildBlocksActive(props.content);
    } else {
      rebuildFinal(props.content);
    }
  },
  { immediate: true, flush: 'post' },
);

watch(copyLabels, () => {
  void nextTick(() => {
    bindCopyButtons(markdownRoot.value, copyLabels.value);
  });
});

async function postProcessDom(): Promise<void> {
  if (props.streaming || blocksActive.value) return;
  await Promise.resolve();
  bindCopyButtons(markdownRoot.value, copyLabels.value);
  await highlightCodeBlocks(markdownRoot.value);
}

watch(finalHtml, () => {
  void postProcessDom();
});

function rehighlightOnThemeChange(): void {
  void highlightCodeBlocks(markdownRoot.value);
}

let themeObserver: MutationObserver | null = null;

onMounted(() => {
  void preloadHighlighter();
  themeObserver = new MutationObserver(rehighlightOnThemeChange);
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
  void postProcessDom();
});

onUnmounted(() => {
  themeObserver?.disconnect();
  themeObserver = null;
});
</script>

<style scoped lang="scss">
.chat-message__markdown {
  font-family: var(--wp-font-head);
  font-size: var(--wp-fs-base);
  line-height: var(--wp-lh-relaxed);

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

.chat-message__md-block {
  width: 100%;
}

/* Queue de stream + curseur collés en fin de texte (pas une ligne en dessous). */
.chat-message__stream-tail {
  display: inline;
}

.chat-message__md-block--tail {
  display: inline;

  :deep(> p) {
    display: inline;
    margin: 0;
  }

  :deep(> p:last-child) {
    margin-bottom: 0;
  }
}

.chat-message__cursor {
  display: inline-block;
  width: 0.55rem;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--primary, var(--wp-accent));
  border-radius: 2px;
  animation: chat-cursor-blink 1s step-end infinite;
}

@media (prefers-reduced-motion: reduce) {
  .chat-message__cursor {
    animation: none;
    opacity: 0.85;
  }
}

@keyframes chat-cursor-blink {
  50% {
    opacity: 0;
  }
}
</style>
