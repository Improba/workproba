import { config } from '@vue/test-utils';
import { vi } from 'vitest';
import { createI18n } from 'vue-i18n';

const i18n = createI18n({
  legacy: false,
  locale: 'en-US',
  fallbackLocale: 'en-US',
  messages: {
    'en-US': {},
    fr: {},
  },
});

config.global.plugins = [i18n];
config.global.mocks = {
  $q: {
    notify: vi.fn(),
    dialog: vi.fn(),
    screen: { lt: {}, gt: {}, xs: false, sm: false, md: true, lg: false, xl: false },
    dark: {
      isActive: false,
      set: vi.fn(),
      toggle: vi.fn(),
    },
    platform: { is: {} },
  },
};
config.global.stubs = {
  'q-btn': true,
  transition: false,
  'transition-group': false,
  teleport: true,
  'router-link': true,
  'router-view': true,
  Lucide: true,
};
