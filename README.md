# Workproba

**Workproba** est un assistant de travail sur dossier local, type Claude Cowork, pour utilisateurs non-codeurs dans le contexte Improba. Application bureau **macOS, Linux, Windows** (Tauri) : l'utilisateur ouvre un dossier projet, l'Imp manipule Word/Excel/PDF en place, avec mémoire locale et sandbox sous le capot.

*Local-first desktop AI cowork assistant — Tauri, RAG, Python sidecar, Vue/Quasar UI.*

## Licence

Workproba est distribué sous **double licence** : usage personnel et éducatif gratuit ([WPEL](./LICENSE)), usage entreprise et institutionnel sur licence commerciale.

Voir [LICENSING.md](./LICENSING.md) pour le guide complet, la FAQ et les contacts.

## Documentation

- [docs/intention.md](./docs/intention.md) : cadrage produit
- [docs/desktop.md](./docs/desktop.md) : architecture bureau
- [docs/architecture.md](./docs/architecture.md) : vue technique
- [docs/workspace-storage.md](./docs/workspace-storage.md) : stockage par workspace
- [desktop/README.md](./desktop/README.md) : développement Tauri

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
- Symlink `.knowledge-base` vers l'IKB Improba

### Développement

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

## Agent IA (Cursor)

`AGENTS.md` → `.knowledge-base/projects/workproba/AGENTS.md`
