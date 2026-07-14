# Signature des installateurs Workproba

> **Statut :** non implémenté (builds non signés en V2)
> **Dernière mise à jour :** 14/07/2026

Les releases actuelles sont **volontairement non signées**. Windows SmartScreen et macOS Gatekeeper affichent un avertissement au premier lancement. C'est documenté pour les utilisateurs dans [installateurs.md](./installateurs.md).

Ce document décrit ce qu'il faudra mettre en place lorsque les certificats Improba seront disponibles.

## Référence interne

Le pipeline de production signé d'**ActoGraph v3** (`actograph-v3/.github/workflows/publish.yml`) sert de modèle :

- Windows : Certum SimplySign (certificat cloud, TOTP)
- macOS : Developer ID Application + notarization Apple
- Vérifications post-build obligatoires (refus d'uploader un binaire non signé)

Workproba utilise **Tauri 2** (pas Electron). Les hooks de signature diffèrent mais les certificats et secrets GitHub sont les mêmes.

## Windows (Authenticode)

### Prérequis

| Secret / variable | Description |
|---|---|
| `CERTUM_OTP_URI` | URI otpauth pour le TOTP SimplySign |
| `CERTUM_USERNAME` | Compte Certum |
| `CERTUM_SUBJECT_FILTER` | Filtre sujet certificat (ex. `Improba`) |

### Scripts à réutiliser ou adapter

Depuis actograph-v3 :

- `.github/scripts/install-simplysign.ps1`
- `.github/scripts/configure-simplysign.ps1`
- `.github/scripts/connect-simplysign.ps1`

Ces scripts installent SimplySign Desktop sur le runner Windows, authentifient via TOTP, et exportent `WIN_CERT_SHA1` (thumbprint du certificat cloud).

### Configuration Tauri

Dans `desktop/src-tauri/tauri.conf.json` :

```json
"windows": {
  "certificateThumbprint": "<thumbprint ou via env>",
  "digestAlgorithm": "sha256",
  "timestampUrl": "http://timestamp.digicert.com"
}
```

Ou via variables d'environnement au build :

- `TAURI_SIGNING_PRIVATE_KEY` (si clé fichier exportée)
- thumbprint SimplySign consommé par `tauri build` / NSIS

### Étape CI à ajouter (dans `desktop-release.yml`, job Windows)

1. Cache + install SimplySign (comme actograph)
2. Authentification TOTP
3. Build Tauri
4. **Vérification** : `Get-AuthenticodeSignature` sur chaque `.exe` / `.msi` produit
5. Cleanup SimplySign en `always()`

Ne jamais publier d'artefacts Windows non signés une fois la signature activée (fail-fast comme actograph).

## macOS (Developer ID + notarization)

### Prérequis

| Secret | Description |
|---|---|
| `MAC_CERT_BASE64` | Certificat `.p12` encodé base64 |
| `CSC_KEY_PASSWORD` | Mot de passe du `.p12` |
| `APPLE_ID` | Apple ID du compte développeur |
| `APPLE_APP_SPECIFIC_PASSWORD` | Mot de passe spécifique à l'application |
| `APPLE_TEAM_ID` | Team ID Apple (ex. `XXXXXXXXXX`) |

### Étape CI à ajouter (jobs macOS)

1. Importer le `.p12` dans un keychain éphémère du runner
2. Exporter `CSC_KEYCHAIN`, `CSC_IDENTITY` (ex. `Developer ID Application: Improba (...)`)
3. Build Tauri avec notarization (`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`)
4. **Vérifications** :
   - `codesign --verify --deep --strict`
   - présence de `Developer ID Application` et du bon `TeamIdentifier`
   - `spctl -a -vv` (Gatekeeper)
5. Cleanup keychain + `.p12` en `always()`

### Configuration Tauri

```json
"macOS": {
  "signingIdentity": "Developer ID Application: Improba (...)",
  "entitlements": "entitlements.plist"
}
```

Un fichier `entitlements.plist` sera à créer selon les besoins (accès fichiers, réseau loopback, etc.).

## Linux

Selon la stratégie de distribution :

| Format | Signature |
|---|---|
| `.deb` | Clé GPG du dépôt APT (optionnel) |
| `.AppImage` | Signature intégrée AppImage (`gpg --detach-sign`) |
| Flatpak | Signature Flathub (hors scope initial) |

Priorité plus basse que Windows et macOS pour la première itération signée.

## Secrets GitHub

Créer un **environment** `deploy` (comme actograph) avec :

- protection par reviewers si souhaité
- secrets listés ci-dessus
- accès restreint au workflow `desktop-release.yml`

## Activation progressive recommandée

1. **Phase 1 (actuelle)** : builds non signés, `releaseDraft: true`, documentation utilisateur
2. **Phase 2** : signature Windows seule + vérification Authenticode
3. **Phase 3** : signature macOS + notarization
4. **Phase 4** : `releaseDraft: false`, checksums SHA256 publiés sur la release

## Checklist avant première release signée

- [ ] Certificat Windows Certum actif et SimplySign testé manuellement
- [ ] Certificat Apple Developer ID valide (expiration > 6 mois)
- [ ] Secrets injectés dans l'environment GitHub `deploy`
- [ ] Build CI vert sur les 4 plateformes avec vérifications de signature
- [ ] Test manuel install + premier lancement sans avertissement OS
- [ ] Mise à jour de [installateurs.md](./installateurs.md) (retirer les sections SmartScreen/Gatekeeper « attendu »)

## Voir aussi

- [installateurs.md](./installateurs.md) : guide utilisateur actuel (non signé)
- [desktop.md](./desktop.md) : architecture desktop et packaging
- `.github/workflows/desktop-release.yml` : pipeline release actuel (build matrix → job `create-release` unique + `SHA256SUMS.txt`)
