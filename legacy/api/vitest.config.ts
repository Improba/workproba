import path from 'node:path';
import swc from 'unplugin-swc';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [
    swc.vite({
      module: { type: 'es6' },
      jsc: {
        parser: {
          syntax: 'typescript',
          decorators: true,
        },
        transform: {
          legacyDecorator: true,
          decoratorMetadata: true,
        },
      },
    }),
  ],
  test: {
    globals: true,
    environment: 'node',
    server: {
      deps: {
        inline: [/@mikro-orm\//, /@nestjs\//],
      },
    },
    include: [
      'test/unit/**/*.spec.ts',
      'test/e2e/**/*.e2e-spec.ts',
    ],
    testTimeout: 10_000,
    pool: 'forks',
    maxWorkers: '50%',
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage',
      reporter: ['text', 'text-summary', 'lcov'],
      include: [
        'src/**/*.controller.ts',
        'src/**/*.service.ts',
        'lib-improba/**/*.controller.ts',
        'lib-improba/**/*.service.ts',
      ],
      exclude: [
        'src/health/**',
        'lib-improba/base/base.controller.ts',
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
      'lib-improba': path.resolve(__dirname, 'lib-improba'),
      '@lib-improba': path.resolve(__dirname, 'lib-improba'),
      '@core': path.resolve(__dirname, 'src/core'),
      '@users': path.resolve(__dirname, 'src/core/users'),
      '@utils': path.resolve(__dirname, 'lib-improba'),
      '@auth-jwt': path.resolve(__dirname, 'lib-improba/modules/auth-jwt'),
      '@test': path.resolve(__dirname, 'test'),
      '@config': path.resolve(__dirname, 'config'),
      src: path.resolve(__dirname, 'src'),
    },
  },
});
