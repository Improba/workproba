<template>
  <div class="browser-panel">
    <div class="browser-panel__toolbar">
        <div class="browser-panel__nav-row">
          <div class="browser-panel__nav">
            <button
              type="button"
              class="browser-panel__nav-btn"
              :aria-label="t('browser.back')"
              :disabled="loading"
              @click="goBack"
            >
              <Lucide name="arrow-left" size="14" color="text-muted" />
            </button>
            <button
              type="button"
              class="browser-panel__nav-btn"
              :aria-label="t('browser.forward')"
              :disabled="loading"
              @click="goForward"
            >
              <Lucide name="arrow-right" size="14" color="text-muted" />
            </button>
            <button
              type="button"
              class="browser-panel__nav-btn"
              :aria-label="t('browser.reload')"
              :disabled="loading"
              @click="refresh"
            >
              <Lucide name="rotate-cw" size="14" color="text-muted" />
            </button>
          </div>
          <button
            type="button"
            class="browser-panel__pilot-btn"
            :class="{ 'browser-panel__pilot-btn--paused': pilotagePaused }"
            @click="togglePilotage"
          >
            <Lucide
              :name="pilotagePaused ? 'play' : 'square'"
              size="12"
              color="text-muted"
            />
            {{ pilotagePaused ? t('browser.resumePilotage') : t('browser.pausePilotage') }}
          </button>
        </div>
        <form class="browser-panel__url-form" @submit.prevent="onNavigate">
          <input
            v-model="urlDraft"
            type="url"
            class="browser-panel__url-input"
            :placeholder="t('browser.urlPlaceholder')"
            :disabled="loading"
          />
          <button
            type="submit"
            class="browser-panel__go-btn"
            :disabled="loading || !urlDraft.trim()"
          >
            {{ t('browser.go') }}
          </button>
        </form>
        <section v-if="visitHistory.length" class="browser-panel__history">
          <header class="browser-panel__history-head">
            <h3 class="browser-panel__history-title">{{ t('browser.historyTitle') }}</h3>
            <button type="button" class="browser-panel__history-clear" @click="clearVisitHistory">
              {{ t('browser.historyClear') }}
            </button>
          </header>
          <ul class="browser-panel__history-list" role="list">
            <li v-for="entry in visitHistory" :key="entry">
              <button type="button" class="browser-panel__history-link" @click="openHistoryUrl(entry)">
                {{ entry }}
              </button>
            </li>
          </ul>
        </section>
      </div>

      <p v-if="pilotagePaused" class="browser-panel__paused" role="status">
        {{ t('browser.pilotagePaused') }}
      </p>

      <p v-if="error" class="browser-panel__error" role="alert">
        {{ errorMessage }}
      </p>

      <div class="browser-panel__scroll">
        <div class="browser-panel__viewport">
          <div
            v-if="loading && !screenshot"
            class="browser-panel__loading"
            role="status"
            :aria-label="loadingMessage"
          >
            <span class="browser-panel__spinner" aria-hidden="true" />
            <p class="browser-panel__loading-title">{{ loadingMessage }}</p>
            <p v-if="showSlowHint" class="browser-panel__loading-hint">
              {{ t('browser.loadingSlow') }}
            </p>
            <p v-if="loadingElapsedSec >= 3" class="browser-panel__loading-hint">
              {{ t('browser.loadingElapsed', { n: loadingElapsedSec }) }}
            </p>
          </div>
          <div v-else-if="screenshot" class="browser-panel__screenshot-wrap">
            <img
              ref="screenshotEl"
              :src="screenshotSrc"
              :alt="title || t('browser.pageView')"
              class="browser-panel__screenshot"
              :class="{ 'browser-panel__screenshot--dimmed': loading }"
              @load="updateScreenshotWidth"
            />
            <div
              v-if="loading"
              class="browser-panel__loading-overlay"
              role="status"
              :aria-label="loadingMessage"
            >
              <span class="browser-panel__spinner" aria-hidden="true" />
              <p class="browser-panel__loading-title">{{ loadingMessage }}</p>
              <p v-if="showSlowHint" class="browser-panel__loading-hint">
                {{ t('browser.loadingSlow') }}
              </p>
            </div>
            <div
              v-if="highlightStyle"
              class="browser-panel__highlight"
              :style="highlightStyle"
              :aria-label="t('browser.highlightRef', { ref: highlight?.ref ?? '' })"
            />
            <div
              v-if="agentTurnActive && !pilotagePaused"
              class="browser-panel__live-badge"
              role="status"
            >
              <span class="browser-panel__live-dot" aria-hidden="true" />
              {{ t('browser.liveView') }}
            </div>
            <div
              v-if="lastAiAction"
              class="browser-panel__action-overlay"
              :aria-label="t('browser.aiActionOverlay')"
            >
              <Lucide name="bot" size="12" color="accent" />
              <span class="browser-panel__action-label">{{ lastAiAction.label }}</span>
            </div>
          </div>
          <div v-else class="browser-panel__empty">
            <Lucide name="globe" size="32" color="text-faint" />
            <p>{{ t('browser.empty') }}</p>
          </div>
        </div>

        <details v-if="snapshotYaml" class="browser-panel__snapshot">
          <summary>{{ t('browser.snapshot') }}</summary>
          <pre class="browser-panel__snapshot-body">{{ snapshotYaml }}</pre>
        </details>

        <details class="browser-panel__ai-hint">
          <summary class="browser-panel__ai-summary">
            <Lucide name="bot" size="14" color="accent" />
            {{ t('browser.aiPilotTitle') }}
          </summary>
          <p class="browser-panel__ai-text">{{ t('browser.aiPilotHint') }}</p>
          <ul class="browser-panel__ai-tools">
            <li>{{ t('browser.aiToolNavigate') }}</li>
            <li>{{ t('browser.aiToolClick') }}</li>
            <li>{{ t('browser.aiToolType') }}</li>
            <li>{{ t('browser.aiToolScroll') }}</li>
            <li>{{ t('browser.aiToolExtract') }}</li>
          </ul>
        </details>
      </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useBrowser } from '@composables/useBrowser';
import { useShellSurfaces } from '@composables/useShellSurfaces';
import { scaleHighlightStyle } from '@utils/browserHighlight';

const BROWSER_TAB_KEY = 'workproba.browser:right_panel';
const SLOW_HINT_DELAY_MS = 2500;
const ELAPSED_TICK_MS = 1000;

const { t } = useI18n();
const { rightPanelTab } = useShellSurfaces();
const {
  currentUrl,
  title,
  screenshot,
  snapshotYaml,
  loading,
  loadingReason,
  loadingStartedAt,
  error,
  pilotagePaused,
  lastAiAction,
  highlight,
  agentTurnActive,
  visitHistory,
  clearVisitHistory,
  init,
  navigate,
  refresh,
  goBack,
  goForward,
  pausePilotage,
  resumePilotage,
} = useBrowser();

const urlDraft = ref('');
const screenshotEl = ref<HTMLImageElement | null>(null);
const screenshotDisplayWidth = ref(0);
const loadingElapsedSec = ref(0);
const showSlowHint = ref(false);
let elapsedTimer: ReturnType<typeof setInterval> | null = null;
let slowHintTimer: ReturnType<typeof setTimeout> | null = null;
let initStarted = false;

const isTabActive = computed(() => rightPanelTab.value === BROWSER_TAB_KEY);

const loadingMessage = computed(() => {
  switch (loadingReason.value) {
    case 'init':
      return t('browser.loadingInit');
    case 'navigate':
      return t('browser.loadingNavigate');
    case 'snapshot':
      return t('browser.loadingSnapshot');
    case 'action':
      return t('browser.loadingAction');
    default:
      return t('common.loading');
  }
});

watch(currentUrl, (url) => {
  if (url) urlDraft.value = url;
});

watch(screenshot, () => {
  updateScreenshotWidth();
});

watch(loading, (isLoading) => {
  clearLoadingTimers();
  if (!isLoading) {
    loadingElapsedSec.value = 0;
    showSlowHint.value = false;
    return;
  }
  loadingElapsedSec.value = 0;
  showSlowHint.value = false;
  elapsedTimer = setInterval(() => {
    if (loadingStartedAt.value) {
      loadingElapsedSec.value = Math.floor((Date.now() - loadingStartedAt.value) / 1000);
    }
  }, ELAPSED_TICK_MS);
  slowHintTimer = setTimeout(() => {
    showSlowHint.value = true;
  }, SLOW_HINT_DELAY_MS);
});

watch(isTabActive, (active) => {
  if (active && !initStarted) {
    initStarted = true;
    void init();
  }
});

const screenshotSrc = computed(() => {
  if (!screenshot.value) return '';
  const raw = screenshot.value;
  if (raw.startsWith('data:')) return raw;
  return `data:image/jpeg;base64,${raw}`;
});

const highlightStyle = computed(() => {
  if (!highlight.value || screenshotDisplayWidth.value <= 0) return null;
  return scaleHighlightStyle(highlight.value, screenshotDisplayWidth.value);
});

const errorMessage = computed(() => {
  if (!error.value) return '';
  if (error.value === 'browser_locked') {
    return t('browser.lockedForbidden');
  }
  if (error.value.includes('playwright') || error.value.includes('chromium')) {
    return t('browser.chromiumRequired');
  }
  return t('browser.errorGeneric');
});

function clearLoadingTimers(): void {
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
  if (slowHintTimer) {
    clearTimeout(slowHintTimer);
    slowHintTimer = null;
  }
}

function updateScreenshotWidth(): void {
  screenshotDisplayWidth.value = screenshotEl.value?.clientWidth ?? 0;
}

let resizeObserver: ResizeObserver | null = null;

function onNavigate(): void {
  void navigate(urlDraft.value.trim());
}

function openHistoryUrl(url: string): void {
  urlDraft.value = url;
  void navigate(url);
}

function togglePilotage(): void {
  if (pilotagePaused.value) {
    resumePilotage();
  } else {
    pausePilotage();
  }
}

onMounted(() => {
  if (isTabActive.value && !initStarted) {
    initStarted = true;
    void init();
  }
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      updateScreenshotWidth();
    });
  }
});

watch(screenshotEl, (el, _prev, onCleanup) => {
  if (!resizeObserver || !el) return;
  resizeObserver.observe(el);
  updateScreenshotWidth();
  onCleanup(() => {
    resizeObserver?.unobserve(el);
  });
});

onUnmounted(() => {
  clearLoadingTimers();
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<style scoped lang="scss">
.browser-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.browser-panel__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-4);
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
  text-align: center;
}

.browser-panel__toolbar {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-bottom: 1px solid var(--wp-border);
}

.browser-panel__nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
}

.browser-panel__nav {
  display: flex;
  gap: var(--wp-space-1);
}

.browser-panel__nav-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.browser-panel__pilot-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  cursor: pointer;
  white-space: nowrap;

  &--paused {
    border-color: color-mix(in srgb, var(--wp-accent) 40%, var(--wp-border));
    color: var(--wp-accent);
  }
}

.browser-panel__url-form {
  display: flex;
  gap: var(--wp-space-2);
}

.browser-panel__url-input {
  flex: 1;
  min-width: 0;
  padding: var(--wp-space-1) var(--wp-space-2);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-mono, monospace);
}

.browser-panel__go-btn {
  padding: var(--wp-space-1) var(--wp-space-2);
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.browser-panel__paused {
  flex: none;
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  background: color-mix(in srgb, var(--wp-accent) 8%, transparent);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
}

.browser-panel__error {
  flex: none;
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  background: color-mix(in srgb, var(--wp-danger) 10%, transparent);
  color: var(--wp-danger);
  font-size: var(--wp-fs-xs);
}

.browser-panel__scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.browser-panel__viewport {
  flex: none;
  background: var(--wp-surface-2);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.browser-panel__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-2);
  width: 100%;
  min-height: 160px;
  padding: var(--wp-space-4);
  text-align: center;
}

.browser-panel__loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--wp-space-2);
  padding: var(--wp-space-3);
  background: color-mix(in srgb, var(--wp-surface) 72%, transparent);
  text-align: center;
}

.browser-panel__spinner {
  width: 1.25rem;
  height: 1.25rem;
  border-radius: var(--wp-r-pill);
  border: 2px solid var(--wp-accent-soft);
  border-top-color: var(--wp-accent);
  animation: browser-panel-spin 0.7s linear infinite;
}

.browser-panel__loading-title {
  margin: 0;
  color: var(--wp-text);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
}

.browser-panel__loading-hint {
  margin: 0;
  color: var(--wp-text-faint);
  font-size: 10px;
  line-height: var(--wp-lh-normal);
}

.browser-panel__screenshot-wrap {
  position: relative;
  max-width: 100%;
}

.browser-panel__screenshot {
  max-width: 100%;
  height: auto;
  display: block;

  &--dimmed {
    opacity: 0.55;
  }
}

.browser-panel__highlight {
  position: absolute;
  box-sizing: border-box;
  border: 2px solid var(--wp-accent);
  background: color-mix(in srgb, var(--wp-accent) 18%, transparent);
  border-radius: 2px;
  pointer-events: none;
  animation: browser-highlight-pulse 1.2s ease-in-out 2;
}

.browser-panel__live-badge {
  position: absolute;
  top: var(--wp-space-2);
  right: var(--wp-space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  padding: 2px var(--wp-space-2);
  border-radius: var(--wp-r-sm);
  background: color-mix(in srgb, var(--wp-surface) 90%, transparent);
  border: 1px solid var(--wp-border);
  font-size: 10px;
  font-weight: 600;
  color: var(--wp-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.browser-panel__live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--wp-accent);
  animation: browser-live-pulse 1.4s ease-in-out infinite;
}

@keyframes browser-panel-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes browser-highlight-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

@keyframes browser-live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.browser-panel__action-overlay {
  position: absolute;
  left: var(--wp-space-2);
  bottom: var(--wp-space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--wp-space-1);
  max-width: calc(100% - var(--wp-space-4));
  padding: var(--wp-space-1) var(--wp-space-2);
  border-radius: var(--wp-r-sm);
  background: color-mix(in srgb, var(--wp-surface) 92%, transparent);
  border: 1px solid var(--wp-border);
  box-shadow: 0 2px 8px rgb(0 0 0 / 12%);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text);
}

.browser-panel__action-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.browser-panel__snapshot,
.browser-panel__ai-hint {
  flex: none;
  border-top: 1px solid var(--wp-border);
  font-size: var(--wp-fs-xs);
}

.browser-panel__snapshot summary,
.browser-panel__ai-hint summary {
  padding: var(--wp-space-2) var(--wp-space-3);
  cursor: pointer;
  color: var(--wp-text-muted);
}

.browser-panel__ai-summary {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  font-weight: 600;
  color: var(--wp-text);
}

.browser-panel__snapshot-body {
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  max-height: 120px;
  overflow: auto;
  font-family: var(--wp-font-mono, monospace);
  font-size: 10px;
  background: var(--wp-surface-2);
  white-space: pre-wrap;
  word-break: break-all;
}

.browser-panel__ai-text {
  margin: 0;
  padding: 0 var(--wp-space-3) var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.browser-panel__ai-tools {
  margin: 0;
  padding: 0 var(--wp-space-3) var(--wp-space-2) calc(var(--wp-space-3) + 1.25rem);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}

.browser-panel__history {
  margin-top: var(--wp-space-2);
  padding: var(--wp-space-2) var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
}

.browser-panel__history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--wp-space-2);
  margin-bottom: var(--wp-space-1);
}

.browser-panel__history-title {
  margin: 0;
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text-muted);
}

.browser-panel__history-clear {
  border: none;
  background: transparent;
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-xs);
  cursor: pointer;

  &:hover {
    color: var(--wp-text-muted);
  }
}

.browser-panel__history-list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 6rem;
  overflow: auto;
}

.browser-panel__history-link {
  display: block;
  width: 100%;
  padding: 2px 0;
  border: none;
  background: transparent;
  color: var(--wp-accent);
  font-size: var(--wp-fs-xs);
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  &:hover {
    text-decoration: underline;
  }
}
</style>
