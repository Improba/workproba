# Workproba installer signing

> **Status:** scripts present; unsigned V2 builds (no-op without certificates)  
> **Last updated:** 15/08/2026

Current releases are **intentionally unsigned**. Windows SmartScreen and macOS Gatekeeper show a warning on first launch. This is documented for users in [installateurs.md](./installateurs.md).

This document describes what to put in place when Improba certificates are available.

## Internal reference

The signed production pipeline from **ActoGraph v3** (`actograph-v3/.github/workflows/publish.yml`) serves as a model:

- Windows: Certum SimplySign (cloud certificate, TOTP)
- macOS: Developer ID Application + Apple notarization
- Mandatory post-build checks (refuse to upload an unsigned binary)

Workproba uses **Tauri 2** (not Electron). Signing hooks differ, but certificates and GitHub secrets are the same.

## Windows (Authenticode)

### Prerequisites

| Secret / variable | Description |
|---|---|
| `CERTUM_OTP_URI` | otpauth URI for SimplySign TOTP |
| `CERTUM_USERNAME` | Certum account |
| `CERTUM_SUBJECT_FILTER` | Certificate subject filter (e.g. `Improba`) |

### Scripts to reuse or adapt

From actograph-v3:

- `.github/scripts/install-simplysign.ps1`
- `.github/scripts/configure-simplysign.ps1`
- `.github/scripts/connect-simplysign.ps1`

These scripts install SimplySign Desktop on the Windows runner, authenticate via TOTP, and export `WIN_CERT_SHA1` (cloud certificate thumbprint).

### Tauri configuration

In `desktop/src-tauri/tauri.conf.json`:

```json
"windows": {
  "certificateThumbprint": "<thumbprint or via env>",
  "digestAlgorithm": "sha256",
  "timestampUrl": "http://timestamp.digicert.com"
}
```

Or via build-time environment variables:

- `TAURI_SIGNING_PRIVATE_KEY` (if using an exported key file)
- SimplySign thumbprint consumed by `tauri build` / NSIS

### CI step to add (in `desktop-release.yml`, Windows job)

1. Cache + install SimplySign (as in actograph)
2. TOTP authentication
3. Tauri build
4. **Verification:** `Get-AuthenticodeSignature` on each produced `.exe` / `.msi`
5. SimplySign cleanup in `always()`

Never publish unsigned Windows artifacts once signing is enabled (fail-fast as in actograph).

## macOS (Developer ID + notarization)

### Prerequisites

| Secret | Description |
|---|---|
| `MAC_CERT_BASE64` | Base64-encoded `.p12` certificate |
| `CSC_KEY_PASSWORD` | `.p12` password |
| `APPLE_ID` | Developer account Apple ID |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password |
| `APPLE_TEAM_ID` | Apple Team ID (e.g. `XXXXXXXXXX`) |

### CI step to add (macOS jobs)

1. Import the `.p12` into an ephemeral runner keychain
2. Export `CSC_KEYCHAIN`, `CSC_IDENTITY` (e.g. `Developer ID Application: Improba (...)`)
3. Build Tauri with notarization (`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`)
4. **Checks:**
   - `codesign --verify --deep --strict`
   - presence of `Developer ID Application` and the correct `TeamIdentifier`
   - `spctl -a -vv` (Gatekeeper)
5. Keychain + `.p12` cleanup in `always()`

### Tauri configuration

```json
"macOS": {
  "signingIdentity": "Developer ID Application: Improba (...)",
  "entitlements": "entitlements.plist"
}
```

Files already in the repo: `desktop/src-tauri/entitlements.plist` (app + sidecar JIT) and `entitlements.chromium-helper.plist`. `signingIdentity` stays `null` until certificates are available.

## Bundled Chromium (Playwright)

Chromium is **not** downloaded at runtime. `scripts/fetch-chromium.sh` places the platform **Chrome for Testing** build in `desktop/src-tauri/resources/ms-playwright/` (gitignored except `.gitkeep`). The tree must contain `chromium-<revision>/` (full browser). A `chromium_headless_shell-*` folder alone is not treated as bundled. The installer copies it; Rust sets `PLAYWRIGHT_BROWSERS_PATH` on the sidecar.

On macOS the nested binaries include `Google Chrome for Testing.app` and Chromium helpers. Task Manager / Activity Monitor may show **Google Chrome for Testing**; that process name cannot be renamed. Sign those nested Mach-Os **before** `tauri build`. Do not resign the `.app` after the `.dmg` is built.

Apple notarization requires signing **every** nested Mach-O (Chromium helpers, framework, PyInstaller sidecar) with Hardened Runtime, **inside-out**, same Team ID as `Workproba.app`.

Without certificates the helper is a **no-op**:

```bash
bash scripts/sign-macos-nested.sh desktop/src-tauri/resources/ms-playwright
bash scripts/sign-macos-nested.sh path/to/Workproba.app
```

When `CODESIGN_IDENTITY` / `CSC_IDENTITY` is set (phase 3):

1. Fetch Chromium, then sign the `ms-playwright` tree **before** `tauri build` (helpers + JIT entitlements in `entitlements.chromium-helper.plist`). The CI release job already does this; without identity it is a no-op.
2. `tauri build` with `signingIdentity` and `entitlements.plist` (JIT for the PyInstaller sidecar). Chromium helpers must already be signed: signing the `.app` after the `.dmg` is built does not update the installer.
3. Notarize + staple the `.dmg` / `.app` as below.
4. Checks: `codesign --verify --deep --strict` and `spctl -a -vv`.

Do not use `com.apple.security.cs.disable-library-validation` on the main app. Helper entitlements are limited to `allow-jit` and `allow-unsigned-executable-memory`.

## Linux

Depending on distribution strategy:

| Format | Signature |
|---|---|
| `.deb` | APT repository GPG key (optional) |
| `.AppImage` | Built-in AppImage signature (`gpg --detach-sign`) |
| Flatpak | Flathub signature (out of initial scope) |

Lower priority than Windows and macOS for the first signed iteration.

## GitHub secrets

Create a **`deploy`** environment (as in actograph) with:

- optional reviewer protection
- secrets listed above
- access restricted to the `desktop-release.yml` workflow

## Recommended progressive rollout

1. **Phase 1 (current):** unsigned builds, `releaseDraft: true`, user documentation
2. **Phase 2:** Windows signing only + Authenticode verification
3. **Phase 3:** macOS signing + notarization
4. **Phase 4:** `releaseDraft: false`, SHA256 checksums published on the release

## Checklist before first signed release

- [ ] Active Windows Certum certificate and SimplySign tested manually
- [ ] Valid Apple Developer ID certificate (expiration > 6 months)
- [ ] Secrets injected into the GitHub `deploy` environment
- [ ] Green CI build on all 4 platforms with signature checks
- [ ] Manual install + first launch test with no OS warning
- [ ] Update [installateurs.md](./installateurs.md) (remove SmartScreen/Gatekeeper "expected" sections)

## See also

- [installateurs.md](./installateurs.md): current user guide (unsigned)
- [desktop.md](./desktop.md): desktop architecture and packaging
- `.github/workflows/desktop-release.yml`: current release pipeline (build matrix → single `create-release` job + `SHA256SUMS.txt`)
