# Workproba installer signing

> **Status:** not implemented (unsigned V2 builds)
> **Last updated:** 14/07/2026

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

An `entitlements.plist` file will need to be created as required (file access, loopback network, etc.).

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
