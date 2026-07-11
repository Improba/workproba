# Stack technique Workproba

> **Dernière mise à jour :** 11/07/2026

## Application bureau

| Composant | Version | Rôle |
|---|---|---|
| Tauri | 2 | Coque bureau (`desktop/`), feature `protocol-asset` pour aperçu fichiers |
| Rust | ≥ 1.77 | Filesystem, stockage workspace, plugins, settings |
| Quasar | 2 | UI webview |
| Vue | 3 | Chat, fichiers, personas, mémoire |
| Python | 3.12 | Sidecar IA (`services/ai/`) |
| SQLite | embarqué | Mémoire locale (RAG + souvenirs `memory.db`) |
| sqlite-vec | 0.1.x | Recherche vectorielle (RAG) |
| Pydantic AI | 2.7 | Agent (chat/agent, outils, streaming) — modèles natifs |
| LiteLLM | 1.x | Embeddings RAG uniquement (Ollama, Mistral, OpenAI…) |
| pdfplumber / python-docx / openpyxl / python-pptx | — | Extraction documents digitaux |

### Ports (développement)

| Service | Port |
|---|---|
| Quasar dev server | `5053` |
| Python sidecar | `8765` |
| Ollama (optionnel) | `11434` |

### Commandes

```bash
make dev              # sidecar + attente /health + Tauri/Quasar (recommandé)
yarn dev              # idem via scripts/dev-all.sh

make dev-ai           # sidecar Python seul
make dev-desktop      # Tauri + Quasar (sidecar déjà lancé ailleurs)
yarn dev:ai-only      # sidecar seul
yarn dev:no-ai        # desktop sans redémarrer le sidecar
```

Logs sidecar en dev : `tail -f .dev-ai.log` à la racine du monorepo.

### Variables front (`front/.env`)

| Variable | Description |
|---|---|
| `AI_SIDECAR_URL` | URL sidecar (défaut `http://127.0.0.1:8765`) |
| `DESKTOP_INTERNAL_SECRET` | Secret partagé avec le sidecar |
| `DESKTOP_MODE` | Toujours `true` |
| `QUASAR_DEV_MODE` | `csr` recommandé |

### Variables AI (`services/ai/.env`)

| Variable | Description |
|---|---|
| `HOST` / `PORT` | Bind sidecar (`127.0.0.1:8765`) |
| `INTERNAL_SECRET` | Secret partagé avec le front |
| `LLM_DEFAULT_*` | Config LLM par défaut (Ollama, etc.) |
| `LLM_EMBEDDING_*` | Config embeddings RAG (`MODEL` requis pour activer le RAG vectoriel) |
| `SANDBOX_TIMEOUT_SECONDS` | Timeout sandbox subprocess |
| `MAX_AGENT_ITERATIONS` | Limite boucle agent |

### Variables dev (racine)

| Variable | Défaut | Rôle |
|---|---|---|
| `AI_PORT` | `8765` | Port du sidecar Python |
| `AI_HOST` | `127.0.0.1` | Host du sidecar |
| `HEALTH_TIMEOUT_S` | `30` | Délai max d'attente de `/health` |
| `AI_SKIP_WAIT` | `0` | `=1` pour ne pas attendre la santé du sidecar |

## Legacy

L'ancien stack web NestJS + Docker est archivé dans `legacy/`. Voir [legacy/README.md](../legacy/README.md).
