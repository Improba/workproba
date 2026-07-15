import eslint from '@eslint/js';
import tseslint from '@typescript-eslint/eslint-plugin';
import tsparser from '@typescript-eslint/parser';
import vueI18n from '@intlify/eslint-plugin-vue-i18n';
import pluginVue from 'eslint-plugin-vue';
import vueParser from 'vue-eslint-parser';
import prettier from 'eslint-config-prettier';
import globals from 'globals';

export default [
  // Ignore patterns (replaces .eslintignore)
  {
    ignores: [
      'dist/**',
      'src-capacitor/**',
      'src-cordova/**',
      '.quasar/**',
      'node_modules/**',
      'quasar.config.*.temporary.compiled*',
    ],
  },
  // Base recommended config
  eslint.configs.recommended,
  // Vue essential rules
  ...pluginVue.configs['flat/essential'],
  // TypeScript files configuration
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        sourceType: 'module',
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ga: 'readonly',
        cordova: 'readonly',
        __statics: 'readonly',
        __QUASAR_SSR__: 'readonly',
        __QUASAR_SSR_SERVER__: 'readonly',
        __QUASAR_SSR_CLIENT__: 'readonly',
        __QUASAR_SSR_PWA__: 'readonly',
        process: 'readonly',
        Capacitor: 'readonly',
        chrome: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
    },
    rules: {
      'prefer-promise-reject-errors': 'off',
      quotes: ['warn', 'single', { avoidEscape: true }],
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-empty-function': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-namespace': 'off',
      'no-unused-vars': 'off',
      'no-undef': 'off',
    },
  },
  // Vue files configuration
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsparser,
        extraFileExtensions: ['.vue'],
        sourceType: 'module',
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ga: 'readonly',
        cordova: 'readonly',
        __statics: 'readonly',
        __QUASAR_SSR__: 'readonly',
        __QUASAR_SSR_SERVER__: 'readonly',
        __QUASAR_SSR_CLIENT__: 'readonly',
        __QUASAR_SSR_PWA__: 'readonly',
        process: 'readonly',
        Capacitor: 'readonly',
        chrome: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
    },
    rules: {
      'prefer-promise-reject-errors': 'off',
      quotes: ['warn', 'single', { avoidEscape: true }],
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-empty-function': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-namespace': 'off',
      'no-unused-vars': 'off',
      'no-undef': 'off',
      'vue/multi-word-component-names': 'off',
      'vue/no-unused-components': 'off',
    },
  },
  // JavaScript files
  {
    files: ['**/*.js', '**/*.cjs', '**/*.mjs'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
  // Vue i18n lint (warn while strings are being extracted — T-V2-2)
  ...vueI18n.configs['flat/base'],
  {
    files: ['src/**/*.vue'],
    ignores: ['src/i18n/**', 'lib-improba/**'],
    plugins: {
      '@intlify/vue-i18n': vueI18n,
    },
    settings: {
      'vue-i18n': {
        // Catalogues en index.ts non supportés par le plugin (issue intlify#32).
        // no-missing-keys s'activera pleinement quand les catalogues seront en JSON.
        messageSyntaxVersion: '^11.0.0',
      },
    },
    rules: {
      '@intlify/vue-i18n/no-raw-text': [
        'error',
        {
          ignorePattern: '^[-#:()&*%+]+$',
          ignoreNodes: ['v-icon', 'q-icon'],
          // User-facing attributes only — skip technical :class, :style, to, :to
          attributes: {
            '/.+/': [
              'title',
              'aria-label',
              'aria-placeholder',
              'aria-roledescription',
              'aria-valuetext',
              'placeholder',
              'alt',
              'label',
            ],
            input: ['placeholder'],
            img: ['alt'],
          },
        },
      ],
      // Catalogues TS (index.ts) : localeDir JSON requis par le plugin (issue intlify#32).
      '@intlify/vue-i18n/no-missing-keys': 'off',
    },
  },
  // P1 extrait en Vague 5b : raw-text en error sur le périmètre ciblé
  {
    files: [
      'src/pages/chat/ChatPage.vue',
      'src/components/workproba/WorkprobaTitleBar.vue',
      'src/components/workproba/KeyboardShortcutsHelp.vue',
      'src/components/settings/AdvancedModelSetup.vue',
      'src/components/workproba/FileExplorer.vue',
    ],
    rules: {
      '@intlify/vue-i18n/no-raw-text': 'error',
    },
  },
  // Prettier config (must be last)
  prettier,
];
