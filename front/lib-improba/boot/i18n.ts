import { createI18n } from 'vue-i18n';
import { App, getCurrentInstance } from 'vue';
import messages from 'src/i18n';

export type MessageLanguages = keyof typeof messages;
// Type-define 'en-US' as the master schema for the resource
export type MessageSchema = (typeof messages)['en-US'];

// See https://vue-i18n.intlify.dev/guide/advanced/typescript.html#global-resource-schema-type-definition
 
declare module 'vue-i18n' {
  // define the locale messages schema
  export interface DefineLocaleMessage extends MessageSchema {}

  // define the datetime format schema
  export interface DefineDateTimeFormat {}

  // define the number format schema
  export interface DefineNumberFormat {}
}
 

export const boot = (options: { app: App<any> }) => {
  const i18n = createI18n({
    locale: 'en-US',
    legacy: false,
    messages,
    globalInjection: true,
  });

  // Set i18n instance on app
  options.app.use(i18n);
  options.app.config.globalProperties.$i18n_ = i18n;
};

export const i18n = (options: { app: App<any> }) => {
  const _i18n = options.app?.config.globalProperties.$i18n_;
  if (!_i18n) {
    throw new Error('boot/i18n: _i18n not initialized');
  }

  return _i18n;
};
