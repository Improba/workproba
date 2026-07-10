# Stack technique Workproba

> **Dernière mise à jour :** 09/07/2026

## Application bureau

| Composant | Version | Rôle |
|---|---|---|
| Tauri | 2 | Coque bureau (`desktop/`) |
| Rust | ≥ 1.77 | Filesystem, stockage workspace |
| Quasar | 2 | UI webview |
| Vue | 3 | Chat, fichiers |
| Python | 3.12 | Sidecar IA (`services/ai/`) |
| SQLite | embarqué | Mémoire locale (RAG `memory.db`) |
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
make dev-ai           # sidecar Python
make dev-desktop      # Tauri + Quasar
```

### Variables front (`front/.env`)

| Variable | Description |
|---|---|
| `AI_SIDECAR_URL` | URL sidecar (défaut `http://127.0.0.1:8765`) |
| `DESKTOP_INTERNAL_SECRET` | Secret optionnel sidecar |
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

## Legacy

L'ancien stack web NestJS + Docker est archivé dans `legacy/`. Voir [legacy/README.md](../legacy/README.md).
