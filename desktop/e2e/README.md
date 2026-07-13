# Desktop e2e tests (WebdriverIO + Tauri)

Tauri desktop shell smoke e2e via the **embedded** WebDriver provider.
Validates the critical path in the native webview (startup, shell, sidecar badge)
on **Linux, Windows, and macOS**, without an external driver.

## Strategy

This smoke is the top layer of a three-tier strategy:

1. **Web front** (Playwright, `front/`): UI/flows without webview.
2. **Front <-> sidecar** (Playwright, `front/playwright.sidecar.config.ts`): badge + SSE without webview.
3. **Python sidecar** (`services/ai/` pytest): agent logic outside webview.
4. **Rust shell** (`src-tauri/` `cargo test`): sidecar liveness, helpers.
5. **Full desktop** (here, WebdriverIO): one critical scenario in the webview, per OS.

We keep this layer intentionally thin: a failure here should not be noisy
from issues already covered by tiers 1 to 4.

## Prerequisites

### 1. Rust WebDriver plugin (debug only)

```bash
cd src-tauri && cargo add tauri-plugin-wdio-webdriver
```

In `src-tauri/src/lib.rs`, make the builder conditional:

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

> The plugin is included only in debug: release builds are not burdened.

### 2. Build the app

```bash
yarn build:debug     # binary: src-tauri/target/debug/workproba-desktop
```

## Running

```bash
yarn test:e2e

# Linux headless
xvfb-run -a yarn test:e2e

# Explicit binary (e.g. release)
APP_BINARY=../src-tauri/target/release/workproba-desktop yarn test:e2e
```

## Cross-platform CI

GitHub Actions matrix:

| OS        | Runner           | Notes                                |
|-----------|------------------|--------------------------------------|
| Linux     | `ubuntu-latest`  | `xvfb-run -a`                        |
| Windows   | `windows-latest` | none (`APP_BINARY=...\.exe`)       |
| macOS     | `macos-latest`   | none (native embedded via WKWebView) |

Excerpt:

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
      # On Linux, wrap with xvfb via a wrapper if headless.
      APP_BINARY: ${{ runner.os == 'Windows' && '../src-tauri/target/debug/workproba-desktop.exe' || '../src-tauri/target/debug/workproba-desktop' }}
```

## Notes

- Mistral LLM is not mocked here. For a full stable chat turn in CI,
  plan for a "fake streaming" mode on the sidecar side (TBD), or limit the smoke to the
  sidecar badge (current case).
- The `embedded` provider avoids `tauri-driver`, `webkit2gtk-driver`, and Edge WebDriver.
  Alternative: `driverProvider: 'external'` (Windows/Linux only).
