<template>
  <q-dialog :model-value="open" @update:model-value="onOpenChange">
    <div class="error-report-dialog">
      <header class="error-report-dialog__head">
        <div>
          <h2 class="error-report-dialog__title">{{ t('errors.reportTitle') }}</h2>
          <p v-if="report" class="error-report-dialog__subtitle">
            {{ t('errors.reportSubtitle') }}
          </p>
        </div>
        <button
          type="button"
          class="error-report-dialog__close"
          :aria-label="t('common.close')"
          @click="close"
        >
          <Lucide name="x" size="16" color="text-muted" />
        </button>
      </header>

      <div v-if="report" class="error-report-dialog__body">
        <p class="error-report-dialog__message">{{ report.message }}</p>
        <span class="error-report-dialog__code">{{ report.code }}</span>

        <label class="error-report-dialog__label" for="error-report-details">
          {{ t('errors.reportDetails') }}
        </label>
        <textarea
          id="error-report-details"
          class="error-report-dialog__details"
          readonly
          :value="detailsBlob"
          rows="10"
          @focus="($event.target as HTMLTextAreaElement).select()"
        />
      </div>

      <footer class="error-report-dialog__foot">
        <button
          v-if="report?.retryable"
          type="button"
          class="error-report-dialog__btn error-report-dialog__btn--ghost"
          @click="runRetry"
        >
          {{ t('common.retry') }}
        </button>
        <button
          type="button"
          class="error-report-dialog__btn error-report-dialog__btn--ghost"
          @click="close"
        >
          {{ t('common.close') }}
        </button>
        <button
          type="button"
          class="error-report-dialog__btn error-report-dialog__btn--ghost"
          @click="onCopy"
        >
          {{ t('errors.reportCopy') }}
        </button>
        <button
          type="button"
          class="error-report-dialog__btn"
          @click="onContactSupport"
        >
          {{ t('errors.reportContact') }}
        </button>
      </footer>
    </div>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { Notify } from 'quasar';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';
import { useErrorReport } from '@composables/useErrorReport';
import { formatErrorReportBlob } from '@utils/errorReport';

const { t } = useI18n();
const { open, report, close, runRetry, copyReport, contactSupport } = useErrorReport();

const detailsBlob = computed(() => (report.value ? formatErrorReportBlob(report.value) : ''));

function onOpenChange(value: boolean): void {
  if (!value) close();
}

async function onCopy(): Promise<void> {
  const ok = await copyReport();
  Notify.create({
    message: ok ? t('errors.reportCopied') : t('errors.reportCopyFailed'),
    color: ok ? 'positive' : 'negative',
    timeout: 2500,
  });
}

async function onContactSupport(): Promise<void> {
  await contactSupport();
}

</script>

<style scoped lang="scss">
.error-report-dialog {
  width: min(520px, 92vw);
  padding: 20px;
  background: var(--wp-surface);
  border-radius: var(--wp-r-md);
  border: 1px solid var(--wp-border);
  box-shadow: var(--wp-shadow-2);
}

.error-report-dialog__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.error-report-dialog__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--wp-text);
}

.error-report-dialog__subtitle {
  margin: 4px 0 0;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
  line-height: var(--wp-lh-relaxed);
}

.error-report-dialog__close {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--wp-r-sm);

  &:hover {
    background: var(--wp-surface-2);
  }
}

.error-report-dialog__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-report-dialog__message {
  margin: 0;
  font-size: var(--wp-fs-sm);
  color: var(--wp-text);
  line-height: var(--wp-lh-relaxed);
}

.error-report-dialog__code {
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: var(--wp-r-sm);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-mono, monospace);
}

.error-report-dialog__label {
  margin-top: 4px;
  font-size: var(--wp-fs-xs);
  color: var(--wp-text-muted);
}

.error-report-dialog__details {
  width: 100%;
  min-height: 180px;
  margin: 0;
  padding: var(--wp-space-2) var(--wp-space-3);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-sm);
  background: var(--wp-bg);
  color: var(--wp-text-muted);
  font-size: var(--wp-fs-xs);
  font-family: var(--wp-font-mono, monospace);
  line-height: 1.45;
  resize: vertical;
  box-sizing: border-box;
}

.error-report-dialog__foot {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.error-report-dialog__btn {
  padding: var(--wp-space-2) var(--wp-space-4);
  border: none;
  border-radius: var(--wp-r-sm);
  background: var(--wp-accent);
  color: var(--wp-on-accent);
  font-size: var(--wp-fs-sm);
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &--ghost {
    background: transparent;
    border: 1px solid var(--wp-border);
    color: var(--wp-text-muted);
    font-weight: 500;
  }
}
</style>
