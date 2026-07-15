<template>
  <div ref="markdownRoot" class="chat-message__markdown">
    <template v-if="props.streaming">
      <div
        v-for="block in stableBlocks"
        :key="`stable-${block.key}`"
        class="chat-message__md-block"
        v-html="block.html"
      />
      <div
        v-if="tailHtml"
        class="chat-message__md-block chat-message__md-block--tail"
        v-html="tailHtml"
      />
    </template>
    <div v-else v-html="finalHtml" />
  </div>
  <span
    v-if="streaming && showCursor"
    class="chat-message__cursor"
    aria-hidden="true"
  />
</template>

<script lang="ts">
export { defaultCodeHtml, sanitizeMarkdownHtml } from '@utils/markdownRender';
</script>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useThrottleFn } from '@vueuse/core';
import {
  bindCopyButtons,
  highlightCodeBlocks,
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

interface RenderBlock {
  key: number;
  html: string;
}

const stableBlocks = ref<RenderBlock[]>([]);
const tailHtml = ref('');
const finalHtml = ref('');
const blockSources = ref<string[]>([]);
const markdownRoot = ref<HTMLElement | null>(null);

const copyLabels = computed(() => ({
  copy: t('chat.codeCopy'),
  copied: t('chat.codeCopied'),
  failed: t('chat.codeCopyFailed'),
}));

function rebuildStreaming(content: string): void {
  const { completeBlocks, tail } = splitMarkdownForStreaming(content);
  const nextStable: RenderBlock[] = [];

  for (let i = 0; i < completeBlocks.length; i++) {
    const source = completeBlocks[i];
    const cached = blockSources.value[i] === source ? stableBlocks.value[i] : null;
    nextStable.push(
      cached ?? {
        key: i,
        html: sanitizeMarkdownHtml(renderMarkdownPlain(source)),
      },
    );
  }

  stableBlocks.value = nextStable;
  blockSources.value = completeBlocks;
  tailHtml.value = tail
    ? sanitizeMarkdownHtml(renderMarkdownPlain(tail))
    : '';
}

function rebuildFinal(content: string): void {
  stableBlocks.value = [];
  blockSources.value = [];
  tailHtml.value = '';
  finalHtml.value = sanitizeMarkdownHtml(renderMarkdownFull(content));
}

function updateRender(): void {
  if (props.streaming) {
    rebuildStreaming(props.content);
  } else {
    rebuildFinal(props.content);
  }
}

const throttledStreamingUpdate = useThrottleFn(() => {
  if (!props.streaming) return;
  rebuildStreaming(props.content);
}, 80, true);

watch(
  () => props.content,
  () => {
    if (props.streaming) {
      void throttledStreamingUpdate();
    } else {
      updateRender();
    }
  },
  { immediate: true },
);

watch(
  () => props.streaming,
  (streaming, wasStreaming) => {
    if (wasStreaming && !streaming) {
      updateRender();
    }
  },
);

watch(copyLabels, () => {
  if (!props.streaming) {
    void postProcessDom();
  }
});

async function postProcessDom(): Promise<void> {
  if (props.streaming) return;
  await Promise.resolve();
  bindCopyButtons(markdownRoot.value, copyLabels.value);
  await highlightCodeBlocks(markdownRoot.value);
}

watch(finalHtml, () => {
  void postProcessDom();
});

function rehighlightOnThemeChange(): void {
  if (props.streaming) return;
  void highlightCodeBlocks(markdownRoot.value);
}

let themeObserver: MutationObserver | null = null;

onMounted(() => {
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
