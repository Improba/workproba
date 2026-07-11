<template>
  <div class="browser-panel">
    <div v-if="!isBrowserPluginActive" class="browser-panel__inactive">
      <Lucide name="globe" size="24" color="text-faint" />
      <p>{{ t('browser.inactive') }}</p>
    </div>

    <template v-else>
      <div class="browser-panel__toolbar">
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
      </div>

      <p v-if="error" class="browser-panel__error" role="alert">
        {{ errorMessage }}
      </p>

      <div class="browser-panel__viewport">
        <p v-if="loading && !screenshot" class="browser-panel__loading">
          {{ t('common.loading') }}
        </p>
        <img
          v-else-if="screenshot"
          :src="screenshotSrc"
          :alt="title || t('browser.pageView')"
          class="browser-panel__screenshot"
        />
        <div v-else class="browser-panel__empty">
          <Lucide name="globe" size="32" color="text-faint" />
          <p>{{ t('browser.empty') }}</p>
        </div>
      </div>

      <details v-if="snapshotYaml" class="browser-panel__snapshot">
        <summary>{{ t('browser.snapshot') }}</summary>
        <pre class="browser-panel__snapshot-body">{{ snapshotYaml }}</pre>
      </details>

      <section class="browser-panel__ai-hint" :aria-label="t('browser.aiPilotTitle')">
        <h3 class="browser-panel__ai-title">
          <Lucide name="bot" size="14" color="accent" />
          {{ t('browser.aiPilotTitle') }}
        </h3>
        <p class="browser-panel__ai-text">{{ t('browser.aiPilotHint') }}</p>
        <ul class="browser-panel__ai-tools">
          <li>{{ t('browser.aiToolNavigate') }}</li>
          <li>{{ t('browser.aiToolClick') }}</li>
          <li>{{ t('browser.aiToolExtract') }}</li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useBrowser } from '@composables/useBrowser';

const { t } = useI18n();
const {
  isBrowserPluginActive,
  currentUrl,
  title,
  screenshot,
  snapshotYaml,
  loading,
  error,
  init,
  navigate,
  refresh,
  goBack,
  goForward,
} = useBrowser();

const urlDraft = ref('');

watch(currentUrl, (url) => {
  if (url) urlDraft.value = url;
});

const screenshotSrc = computed(() => {
  if (!screenshot.value) return '';
  const raw = screenshot.value;
  if (raw.startsWith('data:')) return raw;
  return `data:image/png;base64,${raw}`;
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

function onNavigate(): void {
  void navigate(urlDraft.value.trim());
}

onMounted(() => {
  void init();
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

.browser-panel__inactive,
.browser-panel__empty {
  flex: 1;
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
  color: var(--wp-on-accent, #fff);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.browser-panel__error {
  flex: none;
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  background: color-mix(in srgb, var(--wp-danger) 10%, transparent);
  color: var(--wp-danger);
  font-size: var(--wp-fs-xs);
}

.browser-panel__viewport {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: var(--wp-surface-2);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.browser-panel__loading {
  padding: var(--wp-space-4);
  color: var(--wp-text-faint);
  font-size: var(--wp-fs-sm);
}

.browser-panel__screenshot {
  max-width: 100%;
  height: auto;
  display: block;
}

.browser-panel__snapshot {
  flex: none;
  border-top: 1px solid var(--wp-border);
  font-size: var(--wp-fs-xs);

  summary {
    padding: var(--wp-space-2) var(--wp-space-3);
    cursor: pointer;
    color: var(--wp-text-muted);
  }
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

.browser-panel__ai-hint {
  flex: none;
  padding: var(--wp-space-2) var(--wp-space-3);
  border-top: 1px solid var(--wp-border);
  background: var(--wp-surface);
}

.browser-panel__ai-title {
  display: flex;
  align-items: center;
  gap: var(--wp-space-2);
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  font-weight: 600;
  color: var(--wp-text);
}

.browser-panel__ai-text {
  margin: 0 0 var(--wp-space-1);
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.browser-panel__ai-tools {
  margin: 0;
  padding-left: 1.25rem;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-faint);
}
</style>
