import type { StartPrompt } from './startPrompts.types';
import { t } from '@utils/i18nT';

export type { StartPrompt } from './startPrompts.types';

export function getStartPrompts(): StartPrompt[] {
  return [
    {
      id: 'pdf-summary',
      icon: 'file-text',
      title: t('chat.prompts.pdfSummaryTitle'),
      subtitle: t('chat.prompts.pdfSummarySubtitle'),
      prompt: t('chat.prompts.pdfSummaryPrompt'),
    },
    {
      id: 'search-mentions',
      icon: 'search',
      title: t('chat.prompts.searchTitle'),
      subtitle: t('chat.prompts.searchSubtitle'),
      prompt: t('chat.prompts.searchPrompt'),
    },
    {
      id: 'excel-candidates',
      icon: 'table',
      title: t('chat.prompts.excelTitle'),
      subtitle: t('chat.prompts.excelSubtitle'),
      prompt: t('chat.prompts.excelPrompt'),
    },
    {
      id: 'compare-quotes',
      icon: 'scale',
      title: t('chat.prompts.compareTitle'),
      subtitle: t('chat.prompts.compareSubtitle'),
      prompt: t('chat.prompts.comparePrompt'),
    },
    {
      id: 'invoice-reminder',
      icon: 'mail',
      title: t('chat.prompts.reminderTitle'),
      subtitle: t('chat.prompts.reminderSubtitle'),
      prompt: t('chat.prompts.reminderPrompt'),
    },
    {
      id: 'revenue-chart',
      icon: 'bar-chart-3',
      title: t('chat.prompts.chartTitle'),
      subtitle: t('chat.prompts.chartSubtitle'),
      prompt: t('chat.prompts.chartPrompt'),
    },
  ];
}
