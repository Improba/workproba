# Tests e2e desktop (WebdriverIO + Tauri)

Smoke e2e de la coque bureau Tauri via le fournisseur WebDriver **embedded**.
Valide le parcours critique dans la webview native (démarrage, shell, badge sidecar)
sur **Linux, Windows et macOS**, sans driver externe.

## Stratégie

Ce smoke est la couche la plus haute d'une stratégie en tiers :

1. **Front web** (Playwright, `front/`) — UI/flux sans webview.
2. **Front <-> sidecar** (Playwright, `front/playwright.sidecar.config.ts`) — badge + SSE sans webview.
3. **Sidecar Python** (`services/ai/` pytest) — logique agent hors webview.
4. **Coque Rust** (`src-tauri/` `cargo test`) — liveness sidecar, helpers.
5. **Desktop complet** (ici, WebdriverIO) — un seul scénario critique dans la webview, par OS.

On garde cette couche volontairement mince : un échec ici ne doit pas être bruité
par des problèmes déjà couverts par les tiers 1 à 4.

## Prérequis

### 1. Plugin Rust WebDriver (debug only)

```bash
cd src-tauri && cargo add tauri-plugin-wdio-webdriver
```

Dans `src-tauri/src/lib.rs`, rendre le builder conditionnel :

```rust
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(ProjectState::default())
        .manage(FsWatchState::default());

    #[cfg(debug_assertions)]
    let builder = builder.plugin(tauri_plugin_wdio_webdriver::init());

    builder
        .setup(/* ... */)
        .invoke_handler(/* ... */)
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

> Le plugin n'est inclus qu'en debug : les builds release ne sont pas alourdis.

### 2. Builder l'app

```bash
yarn build:debug     # binaire : src-tauri/target/debug/workproba-desktop
```

## Lancement

```bash
yarn test:e2e

# Linux headless
xvfb-run -a yarn test:e2e

# Binaire explicite (ex: release)
APP_BINARY=../src-tauri/target/release/workproba-desktop yarn test:e2e
```

## CI cross-platform

Matrice GitHub Actions :

| OS        | Runner           | Particularité                        |
|-----------|------------------|--------------------------------------|
| Linux     | `ubuntu-latest`  | `xvfb-run -a`                        |
| Windows   | `windows-latest` | aucune (`APP_BINARY=...\.exe`)       |
| macOS     | `macos-latest`   | aucune (embedded natif via WKWebView) |

Extrait :

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
runs-on: ${{ matrix.os }}
steps:
  - uses: actions/checkout@v4
  - uses: dtolnay/rust-toolchain@stable
  - run: yarn install
  - run: yarn build:debug
  - run: yarn test:e2e
    shell: bash
    env:
      # Sur Linux, encapsuler avec xvfb via un wrapper si headless.
      APP_BINARY: ${{ runner.os == 'Windows' && '../src-tauri/target/debug/workproba-desktop.exe' || '../src-tauri/target/debug/workproba-desktop' }}
```

## Notes

- Le LLM Mistral n'est pas mocké ici. Pour un tour de chat complet et stable en CI,
  prévoir un mode « fake streaming » côté sidecar (à définir), ou limiter le smoke au
  badge sidecar (cas actuel).
- Le fournisseur `embedded` évite `tauri-driver`, `webkit2gtk-driver` et Edge WebDriver.
  Alternative : `driverProvider: 'external'` (Windows/Linux uniquement).
