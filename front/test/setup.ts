import { config } from '@vue/test-utils';
import { createApp } from 'vue';
import { vi } from 'vitest';
import { createI18n } from 'vue-i18n';

import { boot, setLang } from '@boot/i18n';
import enUS from '@i18n/en-US';
import fr from '@i18n/fr';

const i18n = createI18n({
  legacy: false,
  locale: 'fr',
  fallbackLocale: 'fr',
  messages: {
    fr,
    'en-US': enUS,
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

// Initialise le singleton i18n pour les modules utilitaires (i18nT, toolCallDetails, …)
const bootApp = createApp({ template: '<div />' });
boot({ app: bootApp });
setLang('fr');
