# Workproba

> **Status:** Local-first desktop pivot
> **Date:** 14/07/2026
> **Decision maker:** Syl

## Intent

Build **Workproba**, an in-house equivalent of **Claude Cowork**, aimed primarily at **non-coder users**, in the Improba context. Desktop application (macOS, Linux, Windows): the user **opens a space** (a local folder on disk), the Imp (agent) manipulates documents in place, runs code under the hood, and relies on locally indexed memory.

## Product decision

**Tauri 2 desktop application**, local-first. See [desktop.md](./desktop.md).

## Product goals

- Multi-OS desktop: macOS (`.dmg`), Linux (`.AppImage`, `.deb`), Windows (`.msi`).
- **Spaces**: local folder = one space (no upload); renameable display title in sidebar.
- Polished agent chat, human-language action cards, SSE streaming.
- Local memory: RAG per space + explicit user (global) and project (per-space) memories; cross-session promotion from conversation summaries.
- Personas plugin: simulated professional perspectives (opinion, meeting, discussion).
- Automatic versions before file modifications.
- LLM sovereignty: Ollama, vLLM, Mistral cloud, changeable URLs.

## Non-goals (desktop initial release)

- Primary web product.
- IDE / code editor.
- Arbitrary user code.
- Mandatory cloud sync.

## Stack

- **Shell**: Tauri 2 (Rust): `desktop/`
- **UI**: Quasar 2 + Vue 3 + Anubis: `front/`
- **AI**: Python 3.12 + FastAPI sidecar: `services/ai/`
- **Data**: SQLite + `.workproba/` per space in `{app_data}/spaces/` + `{app_data}/user/` for global memory
- **Cloud (optional, archived)**: see `legacy/`

## Phasing

1. Tauri scaffold + folder commands
2. Front: desktop mode, open a space
3. Local Python sidecar (port 8765)
4. Local RAG, extraction, versions
5. Scoped memory, plugins (personas), attachments, document preview
6. Multi-OS packaging
7. Optional cloud sync

## See also

- [desktop.md](./desktop.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)
- [architecture.md](./architecture.md)
- [../desktop/README.md](../desktop/README.md)
