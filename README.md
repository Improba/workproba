# Workproba

L'IA est partout aujourd'hui : un copilote dans Word, un assistant dans Gmail, une fonctionnalité de plus dans chaque logiciel. Nous pensons qu'elle devrait surtout être **votre interface de travail** : une application bureau qui vous connaît, retient ce qui compte pour vous, et agit sur **vos** fichiers et dossiers, sans être enfermée dans un seul outil.

**Workproba** est cet assistant. Vous ouvrez un dossier sur votre ordinateur (un projet, un dossier client, vos documents) et vous travaillez avec lui comme avec un collègue : rédiger, organiser, analyser, modifier Word, Excel ou PDF directement sur place. Disponible sur **macOS, Linux et Windows**. Vos données restent chez vous.

*Assistant de travail IA local. Application bureau, mémoire personnelle, connexion à vos fichiers.*

## Aperçu

| Mode clair | Mode sombre |
|---|---|
| ![Workproba en mode clair, chat, personas et workspace](./docs/images/workproba-light-mode.jpg) | ![Workproba en mode sombre, chat, fichiers et workspace](./docs/images/workproba-dark-mode.jpg) |

## Fonctionnalités (V2)

- **Chat agent** : streaming SSE, modèle et raisonnement par conversation, pièces jointes, menu compositeur « + »
- **Mémoire scopée** : souvenirs utilisateur globaux + souvenirs projet, RAG local, outil agent `remember`
- **Plugin Personas** : avis métiers, réunions simulées, discussions (set Improba builtin)
- **Workspace** : sidebar workspaces/conversations, panneau droit (fichiers, aperçu, personas), side chat
- **Documents** : aperçu HTML/texte via sidecar, images via protocol-asset Tauri, versions avant écriture
- **Plugins** : projet, browser, cloud (extensibles, activables dans les réglages)

## Licence

Workproba est distribué sous **double licence** : usage personnel et éducatif gratuit ([WPEL](./LICENSE)), usage entreprise et institutionnel sur licence commerciale.

Voir [LICENSING.md](./LICENSING.md) pour le guide complet, la FAQ et les contacts.

## Première installation

Téléchargez l'installateur pour votre système (Windows, macOS ou Linux) sur la page **Releases** du dépôt. En V2, les installateurs ne sont pas encore signés numériquement : Windows et macOS affichent un avertissement au premier lancement. C'est normal.

Guide pas à pas (SmartScreen, Gatekeeper, `.deb`, AppImage, désinstallation) : **[docs/installateurs.md](./docs/installateurs.md)**.

## Documentation

- [docs/installateurs.md](./docs/installateurs.md) : installation (grand public)
- [docs/intention.md](./docs/intention.md) : cadrage produit
- [docs/desktop.md](./docs/desktop.md) : architecture bureau
- [docs/architecture.md](./docs/architecture.md) : vue technique
- [docs/memory.md](./docs/memory.md) : mémoire user/projet et RAG
- [docs/plugins.md](./docs/plugins.md) : plugins V2 (personas, projet, …)
- [docs/workspace-storage.md](./docs/workspace-storage.md) : stockage par workspace
- [docs/README.md](./docs/README.md) : index complet de la documentation
- [desktop/README.md](./desktop/README.md) : développement Tauri
- [services/ai/README.md](./services/ai/README.md) : API sidecar Python

## Structure

```
workproba/
├── desktop/          # Coque Tauri (produit)
├── front/            # UI Quasar (webview)
├── services/ai/      # Sidecar Python IA
├── docs/
├── scripts/
└── legacy/           # Ancien stack web (archivé, non utilisé)
```

## Démarrage

### Prérequis

- Rust ≥ 1.77, Node.js ≥ 22.22 (24 recommandé pour vitest 4 / build Quasar), Yarn
- Python 3.12 + uvicorn
- Dépendances OS Tauri : voir [desktop/README.md](./desktop/README.md)

### Développement

#### Une seule commande (recommandé)

Démarre le sidecar Python, attend qu'il soit sain (`/health`), puis lance Tauri qui démarre lui-même Quasar. Un seul `Ctrl+C` arrête proprement les deux.

```bash
make dev          # ou : yarn dev
```

Variantes :

```bash
make dev-ai       # sidecar Python seul
make dev-desktop  # Tauri seul (si sidecar déjà lancé ailleurs)
yarn dev:no-ai    # desktop sans (re)démarrer le sidecar
yarn dev:ai-only  # sidecar Python seul
```

Variables d'environnement utiles :

| Variable | Défaut | Rôle |
|---|---|---|
| `AI_PORT` | `8765` | Port du sidecar Python |
| `AI_HOST` | `127.0.0.1` | Host du sidecar |
| `HEALTH_TIMEOUT_S` | `30` | Délai max d'attente de `/health` |
| `AI_SKIP_WAIT` | `0` | `=1` pour ne pas attendre la santé du sidecar |

Logs du sidecar : `tail -f .dev-ai.log` à la racine.

#### Deux terminaux (méthode historique)

```bash
# Terminal 1 — sidecar Python (:8765)
make dev-ai

# Terminal 2 — Tauri + Quasar (:5053)
make dev-desktop
```

Ou : `bash scripts/dev.sh` puis `cd desktop && yarn dev`

### Build installateur

```bash
cd desktop && yarn build
```
