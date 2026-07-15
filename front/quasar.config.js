// Configuration for your app
// https://v2.quasar.dev/quasar-cli-vite/quasar-config-js

import { configure } from 'quasar/wrappers';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import anubis from 'anubis-ui';
import 'dotenv/config';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const packageJson = readFileSync('./package.json', 'utf-8');
const version = JSON.parse(packageJson).version || 0;
const appname = JSON.parse(packageJson).name;

export default configure(function (/* ctx */) {
  return {
    // https://v2.quasar.dev/quasar-cli-vite/prefetch-feature
    // preFetch: true,

    // app boot file (/src/boot)
    // --> boot files are part of "main.js"
    // https://v2.quasar.dev/quasar-cli-vite/boot-files
    boot: ['lib-improba', 'axios'],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#css
    css: ['app.scss', '_anubis.scss', 'workproba.scss'],

    // https://github.com/quasarframework/quasar/tree/dev/extras
    extras: [
      // 'ionicons-v4',
      'mdi-v7',
      // 'fontawesome-v6',
      // 'eva-icons',
      // 'themify',
      // 'line-awesome',
      // 'roboto-font-latin-ext', // this or either 'roboto-font', NEVER both!

      //'roboto-font', // optional, you are not bound to it
      'material-icons', // optional, you are not bound to it
    ],

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#build
    build: {
      target: {
        browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node24',
      },

      vueRouterMode: process.env.VUE_ROUTER_MODE ?? 'history', // available values: 'hash', 'history'
      // vueRouterBase,
      // vueDevtools,
      // vueOptionsAPI: false,

      // rebuildCache: true, // rebuilds Vite/linter/etc cache on startup

      // publicPath: '/',
      // analyze: true,
      // env: {},
      // rawDefine: {}
      // ignorePublicFolder: true,
      // minify: false,
      // polyfillModulePreload: true,
      // distDir

      extendViteConf(viteConf) {
        Object.assign(viteConf.resolve.alias, {
          '~': resolve(__dirname, './src'),
          '@boot': resolve(__dirname, './src/boot'),
          '@assets': resolve(__dirname, './src/assets'),
          '@components': resolve(__dirname, './src/components'),
          '@composables': resolve(__dirname, './src/composables'),
          '@capabilities': resolve(__dirname, './src/capabilities'),
          '@css': resolve(__dirname, './src/css'),
          '@i18n': resolve(__dirname, './src/i18n'),
          '@layouts': resolve(__dirname, './src/layouts'),
          '@pages': resolve(__dirname, './src/pages'),
          '@router': resolve(__dirname, './src/router'),
          '@services': resolve(__dirname, './src/services'),
          '@utils': resolve(__dirname, './src/utils'),
          '@lib-improba': resolve(__dirname, './lib-improba'),
          '#types': resolve(__dirname, './src/types'),
        });
      },

      // viteVuePluginOptions: {},

      vitePlugins: [
        anubis.plugin,
        [
          '@intlify/unplugin-vue-i18n/vite',
          {
            // if you want to use Vue I18n Legacy API, you need to set `compositionOnly: false`
            // compositionOnly: false,

            // if you want to use named tokens in your Vue I18n messages, such as 'Hello {name}',
            // you need to set `runtimeOnly: false`
            runtimeOnly: false,

            // you need to set i18n resource including paths !
            include: resolve(__dirname, './src/i18n/**'),
          },
        ],
        [
          'vite-plugin-checker',
          {
            // vue-tsc 3.x has compatibility issues with vite-plugin-checker
            // Use `yarn type-check:file` manually instead
            // vueTsc: { tsconfigPath: 'tsconfig.vue-tsc.json' },
            
            // ESLint 9 flat config not compatible with vite-plugin-checker yet
            // Run `yarn lint` separately
          },
          { server: false },
        ],
      ],
      env: {
        // dev
        API_URL: process.env.API_URL, // 'http://localhost:3000',
        APP_VERSION: version,
        APP_NAME: appname,
        VUE_ROUTER_MODE: process.env.VUE_ROUTER_MODE || 'history',
        DEFAULT_COLOR_MODE: process.env.DEFAULT_COLOR_MODE || 'light',
        // Public site URL (used for SSR error pages' canonical link)
        SITE_URL: process.env.SITE_URL || 'http://localhost:3000',
        // Bureau Tauri
        AI_SIDECAR_URL: process.env.AI_SIDECAR_URL || 'http://127.0.0.1:8765',
        DESKTOP_INTERNAL_SECRET:
          process.env.DESKTOP_INTERNAL_SECRET || 'desktop-dev-secret',
        DESKTOP_MODE: process.env.DESKTOP_MODE || 'true',
      },
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#devServer
    devServer: {
      // https: true
      //open: true, // opens browser window automatically
      client: {
        webSocketURL: `ws://127.0.0.1:${
          process.env.FRONT_DOCKER_PORT_EXPOSED &&
          process.env.FRONT_DOCKER_PORT_EXPOSED !== ''
            ? process.env.FRONT_DOCKER_PORT_EXPOSED
            : '5053'
        }/ws`,
      },
      port:
        process.env.FRONT_DOCKER_PORT_EXPOSED &&
        process.env.FRONT_DOCKER_PORT_EXPOSED !== ''
          ? parseInt(process.env.FRONT_DOCKER_PORT_EXPOSED)
          : 5053,
      strictPort: true, // throws error if port is already in use
    },

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#framework
    framework: {
      config: {},

      // iconSet: 'material-icons', // Quasar icon set
      // lang: 'en-US', // Quasar language pack

      // For special cases outside of where the auto-import strategy can have an impact
      // (like functional components as one of the examples),
      // you can manually specify Quasar components/directives to be available everywhere:
      //
      // components: [],
      // directives: [],

      // Quasar plugins
      // Notify: Print notification
      // Dialog: Dialog box
      // Screen: Screen information
      // Meta: Meta information for SEO
      plugins: ['Notify', 'Dialog', 'Screen', 'Meta'],
    },

    // animations: 'all', // --- includes all animations
    // https://v2.quasar.dev/options/animations
    animations: [],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-js#sourcefiles
    // sourceFiles: {
    //   rootComponent: 'src/App.vue',
    //   router: 'src/router/index',
    //   store: 'src/store/index',
    //   registerServiceWorker: 'src-pwa/register-service-worker',
    //   serviceWorker: 'src-pwa/custom-service-worker',
    //   pwaManifestFile: 'src-pwa/manifest.json',
    //   electronMain: 'src-electron/electron-main',
    //   electronPreload: 'src-electron/electron-preload'
    // },

    // https://v2.quasar.dev/quasar-cli-vite/developing-ssr/configuring-ssr
    ssr: {
      // ssrPwaHtmlFilename: 'offline.html', // do NOT use index.html as name!
      // will mess up SSR

      // extendSSRWebserverConf (esbuildConf) {},
      // extendPackageJson (json) {},

      pwa: false,
      prefetch: true,

      // manualStoreHydration: true,
      // manualPostHydrationTrigger: true,

      prodPort: 3000, // The default port that the production server should use
      // (gets superseded if process.env.PORT is specified at runtime)

      middlewares: [
        'spa-shell-fallback',
        'render', // keep this as last one
      ],
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-pwa/configuring-pwa
    pwa: {
      workboxMode: 'generateSW', // or 'injectManifest'
      injectPwaMetaTags: true,
      swFilename: 'sw.js',
      manifestFilename: 'manifest.json',
      useCredentialsForManifestTag: false,
      // useFilenameHashes: true,
      // extendGenerateSWOptions (cfg) {}
      // extendInjectManifestOptions (cfg) {},
      // extendManifestJson (json) {}
      // extendPWACustomSWConf (esbuildConf) {}
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-cordova-apps/configuring-cordova
    cordova: {
      // noIosLegacyBuildFlag: true, // uncomment only if you know what you are doing
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-capacitor-apps/configuring-capacitor
    capacitor: {
      hideSplashscreen: true,
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-electron-apps/configuring-electron
    electron: {
      // extendElectronMainConf (esbuildConf)
      // extendElectronPreloadConf (esbuildConf)

      inspectPort: 5858,

      bundler: 'packager', // 'packager' or 'builder'

      packager: {
        // https://github.com/electron-userland/electron-packager/blob/master/docs/api.md#options
        // OS X / Mac App Store
        // appBundleId: '',
        // appCategoryType: '',
        // osxSign: '',
        // protocol: 'myapp://path',
        // Windows only
        // win32metadata: { ... }
      },

      builder: {
        // https://www.electron.build/configuration/configuration

        appId: 'front',
      },
    },

    // Full list of options: https://v2.quasar.dev/quasar-cli-vite/developing-browser-extensions/configuring-bex
    bex: {
      contentScripts: ['my-content-script'],

      // extendBexScriptsConf (esbuildConf) {}
      // extendBexManifestJson (json) {}
    },
  };
});
