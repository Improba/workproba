# Workproba technical stack

> **Last updated:** 20/07/2026

## Desktop application

| Component | Version | Role |
|---|---|---|
| Tauri | 2 | Desktop shell (`desktop/`), `protocol-asset` feature for file preview |
| Rust | ≥ 1.77 | Filesystem, workspace storage, plugins, settings |
| Quasar | 2 | Webview UI |
| Vue | 3 | Chat, files, personas, memory |
| Python | 3.12 | AI sidecar (`services/ai/`) |
| SQLite | embedded | Local memory (RAG + `memory.db` memories) |
| sqlite-vec | 0.1.x | Vector search (RAG) |
| Pydantic AI | 2.7 | Agent (chat/agent, tools, streaming): native models |
| LiteLLM | 1.x | RAG embeddings only (Ollama, Mistral, OpenAI…) |
| pdfplumber / python-docx / openpyxl / python-pptx | | Digital document extraction and native Office generation (DOCX, XLSX, PPTX via `write_*` tools) |

### Ports (development)

| Service | Port |
|---|---|
| Quasar dev server | `5053` |
| Python sidecar | `8765` |
| Ollama (optional) | `11434` |

### Commands

```bash
make dev              # sidecar + wait for /health + Tauri/Quasar (recommended)
yarn dev              # same via scripts/dev-all.sh

make dev-ai           # Python sidecar only
make dev-desktop      # Tauri + Quasar (sidecar already running elsewhere)
yarn dev:ai-only      # sidecar only
yarn dev:no-ai        # desktop without restarting the sidecar
```

Sidecar logs in dev: `tail -f .dev-ai.log` at the monorepo root.

### Front variables (`front/.env`)

| Variable | Description |
|---|---|
| `AI_SIDECAR_URL` | Sidecar URL (default `http://127.0.0.1:8765`) |
| `DESKTOP_INTERNAL_SECRET` | Shared secret with the sidecar |
| `DESKTOP_MODE` | Always `true` |
| `QUASAR_DEV_MODE` | `csr` recommended |
| `VITE_CLOUD_WEB_URL` | Improba Cloud web console URL for login/register links (default `http://localhost:8482`; see `cloudWebUrls.ts`) |

**CORS (cloud dev):** when the desktop Quasar dev server runs on `:5053`, set `CORS_ORIGINS` on the cloud API (CSV, e.g. `http://localhost:8080,http://localhost:5053`) so browser calls from the desktop webview are allowed. Falls back to `FRONTEND_URL` when unset.

### AI variables (`services/ai/.env`)

| Variable | Description |
|---|---|
| `HOST` / `PORT` | Sidecar bind (`127.0.0.1:8765`) |
| `INTERNAL_SECRET` | Shared secret with the front |
| `LLM_DEFAULT_*` | Default LLM config (Ollama, etc.) |
| `LLM_EMBEDDING_*` | RAG embedding config (`MODEL` required to enable vector RAG) |
| `MEMORY_RANKING_*`, `MEMORY_EMBEDDING_CACHE_MAX_ENTRIES` | Hybrid memory/session ranking + embedding LRU cache (see [memory.md](./memory.md)) |
| `SANDBOX_TIMEOUT_SECONDS` | Subprocess sandbox timeout |
| `MAX_AGENT_ITERATIONS` | Agent loop limit |

### Dev variables (root)

| Variable | Default | Role |
|---|---|---|
| `AI_PORT` | `8765` | Python sidecar port |
| `AI_HOST` | `127.0.0.1` | Sidecar host |
| `HEALTH_TIMEOUT_S` | `30` | Max wait for `/health` |
| `AI_SKIP_WAIT` | `0` | `=1` to skip sidecar health wait |

## Legacy

The former NestJS + Docker web stack is archived in `legacy/`. See [legacy/README.md](../legacy/README.md).
