# Workproba Desktop

Coque bureau **Tauri 2** d'Workproba, ciblant **macOS**, **Linux** et **Windows**.

L'UI réutilise le front **Quasar** (`../front/`) en webview. Le cœur IA reste en **Python** (`../services/ai/`) lancé en sidecar. Le Rust ne porte que le pont natif (fenêtre, dialogue de dossier, permissions OS, cycle de vie du sidecar).

## Prérequis

| Outil | Version | Usage |
|---|---|---|
| Rust | ≥ 1.77 | Coque Tauri (`src-tauri/`) |
| Node.js | ≥ 22.22 (24 recommandé) | CLI Tauri + build Quasar (vitest 4 requiert Node ≥ 22.22) |
| Yarn | via front | Dev server Quasar sur le port `5053` |
| Dépendances OS Linux | webkit2gtk, etc. | Voir [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) |

Sur Linux (Debian/Ubuntu) :

```bash
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

## Développement

Depuis la racine `workproba/` :

```bash
make dev-ai        # sidecar Python (port 8765)
make dev-desktop   # Tauri + Quasar (port 5053)
```

Ou depuis `desktop/` :

```bash
yarn dev
```

Cette commande :
1. démarre Quasar (`../front`, port `5053`) via `beforeDevCommand` ;
2. compile la coque Rust (`src-tauri/`, mode debug) ;
3. lance la fenêtre Tauri pointant sur `http://localhost:5053`.

Le service Python IA doit être lancé séparément en dev (voir ci-dessous).

### Rebuild et hot reload

`make dev-desktop` exécute `tauri dev`, qui intègre le watch Rust (pas besoin de `cargo watch` à part).

| Zone modifiée | Rebuild Rust ? | Hot reload |
|---|---|---|
| `front/` (Vue, TS, CSS) | non | oui (HMR Quasar) |
| `desktop/src-tauri/` (Rust) | oui (incrémental Cargo) | non : recompile et **redémarre la fenêtre** |
| `services/ai/` (Python) | non | oui si lancé via `make dev-ai` (`uvicorn --reload`) |

Points utiles :

- **Premier lancement** : compilation Rust complète, potentiellement longue. Les builds suivants sont incrémentaux.
- **Rust** : pas de hot reload in-process. Tauri surveille les `.rs` et relance l'app après recompilation. L'état de la fenêtre (dossier ouvert, etc.) est perdu au redémarrage.
- **Frontend** : la webview charge le dev server Quasar ; les changements Vue/TS se reflètent sans redémarrer Tauri.
- **Python** : indépendant de `make dev-desktop`. Lancer `make dev-ai` dans un autre terminal.

### Service Python (dev)

```bash
cd ../services/ai && ./run_dev.sh
# ou : make dev-ai (depuis la racine workproba/)
```

Le chat appelle le sidecar Python **directement** en HTTP (`127.0.0.1:8765`), sans passer par Rust.

En dev, Tauri tente aussi de **démarrer automatiquement** le sidecar (`try_spawn_dev_uvicorn`) : il utilise en priorité `services/ai/.venv/bin/python -m uvicorn`, puis `services/ai/.venv/bin/uvicorn`, avec repli sur `python3 -m uvicorn` système. La commande `ai_sidecar_status` fait un test de liveness TCP sur `127.0.0.1:8765` et alimente le badge de santé du front (`useSidecarHealth`).

## Build multi-plateforme

```bash
yarn build
```

Cibles configurées : `deb`, `rpm`, `appimage`, `msi`, `nsis`, `dmg`, `app`.

Le packaging du sidecar Python (`workproba-ai`) sera ajouté via `externalBin` une fois le binaire PyInstaller prêt pour chaque triple (`x86_64-unknown-linux-gnu`, `aarch64-apple-darwin`, `x86_64-pc-windows-msvc`, etc.).

## Commandes Tauri exposées au front

| Commande | Rôle |
|---|---|
| `pick_project_folder` | Dialogue natif « Ouvrir un dossier » |
| `set_active_project_path` | Active un dossier, enregistre le workspace (`WorkspaceInfo`) |
| `get_active_project_path` | Retourne le dossier actif |
| `get_workspace_data_dir` | Chemin `.workproba` système pour un dossier |
| `list_workspaces` | Liste les workspaces connus |
| `list_conversations` / `save_conversation` | Sessions chat sur disque |
| `list_documents` | Liste les fichiers du projet (hors dotfiles) |
| `open_path` | Ouvre un fichier ou dossier avec l'application OS |
| `restore_last_project_path` | Restaure le dernier dossier ouvert (persisté app data) |
| `start_ai_sidecar` | Démarre le binaire Python empaqueté (prod) |
| `ai_sidecar_status` | Liveness TCP du sidecar (`127.0.0.1:8765`) pour le badge de santé du front |

Appel depuis Quasar :

```typescript
import { invoke } from '@tauri-apps/api/core';

const path = await invoke<string | null>('pick_project_folder');
```

## Structure

```
desktop/
├── package.json
├── src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs
│   │   ├── commands/project.rs   # filesystem + dossier projet
│   │   └── sidecar.rs            # lancement Python
│   ├── binaries/                 # sidecars empaquetés (build CI)
│   ├── capabilities/
│   └── tauri.conf.json
└── README.md
```

## Voir aussi

- [docs/desktop.md](../docs/desktop.md) : architecture bureau complète
- [docs/architecture.md](../docs/architecture.md) : vue d'ensemble produit
