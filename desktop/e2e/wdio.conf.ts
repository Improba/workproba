import type { Options } from '@wdio/types';

/**
 * Config WebdriverIO pour le smoke e2e desktop Tauri (fournisseur embedded).
 *
 * Prérequis (une seule fois, côté Rust) :
 *   1. cd src-tauri && cargo add tauri-plugin-wdio-webdriver
 *   2. Dans src/lib.rs, en debug uniquement :
 *        #[cfg(debug_assertions)]
 *        let builder = builder.plugin(tauri_plugin_wdio_webdriver::init());
 *   3. Builder l'app : `yarn build:debug` (binaire dans src-tauri/target/debug/...)
 *
 * Lancement :
 *   yarn test:e2e                  # Linux headless : xvfb-run -a yarn test:e2e
 *   APP_BINARY=../src-tauri/target/debug/workproba-desktop yarn test:e2e
 *
 * CI : matrice ubuntu/windows/macos. Sur Linux, `xvfb-run -a`. Le fournisseur
 * embedded n'a besoin d'aucun driver externe sur les trois OS.
 */

const appBinary =
  process.env.APP_BINARY ?? '../src-tauri/target/debug/workproba-desktop';

export const config: Options.Testrunner = {
  runner: 'local',
  specs: ['./e2e/smoke.spec.ts'],
  maxInstances: 1,
  capabilities: [
    {
      browserName: 'tauri',
      'tauri:options': {
        application: appBinary,
      },
    } as never,
  ],
  logLevel: 'warn',
  services: [
    [
      '@wdio/tauri-service',
      {
        driverProvider: 'embedded',
      },
    ],
  ],
  framework: 'mocha',
  mochaOpts: {
    ui: 'bdd',
    timeout: 120000,
  },
  reporters: ['spec'],
};
