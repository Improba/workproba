import vue from '@vitejs/plugin-vue';
import path from 'node:path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'happy-dom',
    include: [
      'test/unit/**/*.spec.ts',
      'test/e2e/**/*.e2e-spec.ts',
    ],
    setupFiles: ['test/setup.ts'],
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage',
      reporter: ['text', 'text-summary', 'lcov'],
      include: [
        'src/layouts/**/*.vue',
        'src/pages/**/*.vue',
        'src/router/**/*.ts',
        'src/services/**/*.ts',
        'src/utils/**/*.ts',
        'lib-improba/composables/use-auth/**/*.ts',
        'lib-improba/utils/**/*.ts',
        'lib-improba/components/mastok/**/*.vue',
      ],
      exclude: [
        '**/*.spec.ts',
        '**/*.interface.ts',
        '**/services/utils/entity.interface.ts',
        'src/pages/adminspace/**',
        'src/pages/auth/**',
        'src/pages/userspace/**',
        'src/pages/QuoteAnimation.vue',
        'src/router/routes/**',
        'lib-improba/pages/demo/**',
        'lib-improba/components/layouts/**',
        'lib-improba/components/utils/**',
        'lib-improba/components/mastok/{MCard,MChip,MCollapse,MDialog,MFilterTable,MInput,MPage,MRange,MSlider,MTable,MToggle,MBtnDropdown,Lucide}.vue',
        'lib-improba/composables/{use-query-param-search,use-query-params,use-rules,use-theme,use-improba-init}.ts',
        'lib-improba/composables/use-auth/{axios,router}.ts',
        'lib-improba/utils/{dialog,file,notify,pagination,q-table-types,style,table-query-params,table-types,type-aliases,export,date-format}.utils.ts',
      ],
      thresholds: {
        branches: 60,
        functions: 70,
        lines: 70,
        statements: 70,
      },
    },
  },
  resolve: {
    alias: {
      '~': path.resolve(__dirname, 'src'),
      // Mirrors l'alias `src` ajouté par le preset Vite de Quasar ; requis pour
      // résoudre les imports internes de `lib-improba` de la forme
      // `src/../lib-improba/...` dans la suite de tests.
      'src': path.resolve(__dirname, 'src'),
      boot: path.resolve(__dirname, 'src/boot'),
      '@assets': path.resolve(__dirname, 'src/assets'),
      '@components': path.resolve(__dirname, 'src/components'),
      '@composables': path.resolve(__dirname, 'src/composables'),
      '@css': path.resolve(__dirname, 'src/css'),
      '@i18n': path.resolve(__dirname, 'src/i18n'),
      '@layouts': path.resolve(__dirname, 'src/layouts'),
      '@pages': path.resolve(__dirname, 'src/pages'),
      '@router': path.resolve(__dirname, 'src/router'),
      '@services': path.resolve(__dirname, 'src/services'),
      '@lib-improba': path.resolve(__dirname, 'lib-improba'),
      '@utils': path.resolve(__dirname, 'src/utils'),
      '@boot': path.resolve(__dirname, 'src/boot'),
      '#types': path.resolve(__dirname, 'src/types'),
    },
  },
});
