# Workproba Desktop

> **Status:** Product decision: desktop pivot
> **Last updated:** 14/07/2026

## Decision

Workproba becomes a **local-first desktop application** (Claude Cowork style), multi-platform:

| OS | Target formats |
|---|---|
| macOS | `.app`, `.dmg` |
| Linux | `.deb`, `.rpm`, `.AppImage` |
| Windows | `.msi`, `.exe` (NSIS) |

Chosen technology: **Tauri 2** (lightweight Rust shell + system webview + existing Quasar UI).

The AI agent remains in **Python** (sidecar). Rust does not replace Python: it provides the native bridge (filesystem, window, permissions, packaging).

## Product metaphor (non-coders)

The user **opens a space** (a local folder on disk). The Imp (agent) works inside it:

- reads and modifies Word, Excel, PDF;
- runs code **under the hood** in a local subprocess sandbox;
- relies on **memory** indexed from folder documents.

Main UI concepts:

| Displayed concept | Meaning |
|---|---|
| **Space** | A local folder the user works in (display title renameable in sidebar) |
| **Conversation** | Exchange with the Imp |
| **Memory** | What the tool knows about the space (per-space RAG + user/project memories) |
| **Personas** | Simulated professional perspectives (plugin: opinion / meeting / discussion) |

## Desktop architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Quasar + Anubis (Tauri webview)                            │
│  chat · files · results                                     │
└──────────────┬──────────────────────────┬───────────────────┘
               │ fetch SSE                  │ invoke() Tauri
               ▼                            ▼
┌──────────────────────────┐    ┌─────────────────────────────┐
│  Python sidecar          │    │  Tauri / Rust               │
│  127.0.0.1:8765          │    │  folder · open_path · etc.  │
│  agent · RAG · sandbox   │    └──────────────┬──────────────┘
└──────────────┬───────────┘                   │ read/write
               │                                ▼
               ▼                    ┌─────────────────────────────┐
┌──────────────────────────┐       │  User project folder        │
│  LLM (Ollama/vLLM/…)     │       │  User project folder        │
└──────────────────────────┘       └─────────────────────────────┘
               │
               ▼
┌──────────────────────────┐
│  {app_data}/spaces/      │
│  {id}/.workproba/        │
└──────────────────────────┘
```

Chat **does not go through Rust**: the Quasar webview calls the Python sidecar directly over HTTP/SSE. Tauri handles native filesystem (open a space via folder picker, list files, open a document).

### Per-space storage

Workproba metadata lives in the **application folder**, not in the client folder. See [workspace-storage.md](./workspace-storage.md).

```
{app_data}/spaces/{workspace_id}/.workproba/
├── manifest.json
├── conversations/
├── versions/
├── attachments/
└── memory.db          # project RAG + explicit memories

{app_data}/user/memory.db   # global user memories
{app_data}/plugins/         # plugin data (personas, …)
```

## Message flow (desktop)

```
[Quasar webview] --HTTP SSE--> [Python sidecar :8765]
       │
       └── invoke Tauri (folder, open_path): outside chat path
```

1. The user opens a space (folder picker dialog; UI label: "Open a space").
2. Tauri registers the space (stable `workspace_id` + path + display title); the front keeps the path and `workspace_id`. The user can rename the display title in the sidebar (`update_workspace_title`).
3. The user sends a message in chat.
4. Quasar calls `POST http://127.0.0.1:8765/agent/turn` (direct SSE). The payload
   includes the active **provider set** with conversation **model + reasoning**
   overrides (persisted in session), clamped against the set model catalogue.
   See [provider-sets-reasoning.md](./provider-sets-reasoning.md).
5. Python runs the agent loop: LLM, file tools, local search, subprocess sandbox.
6. Before sensitive actions (file write, publish, network, code execution), the sidecar
   emits `confirmation_request` (effect-oriented headline + protections). The user approves
   or denies in `ConfirmationCard`; the front calls `POST /agent/confirm`. On deny or
   timeout, the model receives a `ModelRetry` and can adapt.
7. SSE events are shown in chat (tokens, reasoning with spinner, tool calls, `work_*`
   business events); sessions are persisted in `{app_data}/spaces/{id}/.workproba/conversations/`.

**No web server** in the product path. The former NestJS stack is in `legacy/`.

## Roles by layer

| Layer | Language | Role |
|---|---|---|
| UI | TypeScript / Quasar | Chat, files, results, onboarding |
| Desktop shell | Rust / Tauri | Window, OS APIs, filesystem, packaging |
| AI core | Python / FastAPI | Agent loop, extraction, RAG, subprocess sandbox |
| Local data | `{app_data}/spaces/{id}/.workproba/` | Sessions, versions, memory |
| Cloud (archived) | `legacy/` | Former NestJS stack |

## Security and trust (UX)

- **Human Approval Gate (effect-oriented)**: before file writes, publishing, network access,
  code execution, or external sync, the agent pauses and shows a confirmation card in human
  language (e.g. "I will modify: Budget_2026.xlsx") with active safeguards (preview,
  automatic version, no network). Implemented in `app/agent/effects.py` +
  `ConfirmationGate.request_effect()`; UI: `ConfirmationCard.vue`. See
  [architecture.md § Human approval](./architecture.md#human-approval-and-work-events).
- **Automatic versions**: copy to `.workproba/versions/` before write (Python `LocalProjectClient`),
  in addition to user confirmation on modifications.
- **Scope**: the agent does not leave the project folder.
- **Sandbox**: local Python subprocess, no network, configurable timeout.
- **Sidecar**: reachable on loopback only (`127.0.0.1`, `::1`).
- **Audit**: `approval.requested` / `approval.resolved` events when audit is enabled.

## Python packaging (sidecar)

In production: PyInstaller → `workproba-ai-<triple>` binary in `desktop/src-tauri/binaries/`, referenced by `bundle.externalBin`.

In development: `make dev-ai` or `services/ai/run_dev.sh` (port `8765`).

## Phasing

| Phase | Status | Content |
|---|---|---|
| **A** | Done | Tauri scaffold, folder commands, docs |
| **B** | Done | Open a space UI, file list, local sessions |
| **C** | Done | Direct Python SSE, `LocalProjectClient`, subprocess sandbox |
| **D** | Done | SQLite RAG, Office extraction, sidecar monitoring |
| **D+** | Done | Scoped user/project memory, plugins (personas), attachments, document preview, audit, Human Approval Gate (effect-oriented), Work Event Bus (`work_*` SSE) |
| **E** | Done | Multi-OS packaging + PyInstaller sidecar (`scripts/build-sidecar.sh`, CI `desktop-release.yml`) |
| **F** | To do | Optional cloud sync (NestJS) |

### Phase D: validation

- **Sidecar (Python)**: streaming chat, file tools, RAG, scoped memory, personas plugins, work events, effect gate. pytest: **634 tests** (see [testing.md](./testing.md)).
- **Rust shell**: venv-aware sidecar spawn + `ai_sidecar_status` + `protocol-asset` for image preview. `cargo check` OK.
- **Front**: `WorkprobaLayout` (sidebar, right panel, side chat), `useSidecarHealth`, personas plugin integrated in composer.
- **End-to-end desktop run**: `make dev`, open a space, test chat, memory, personas, document preview, confirmation on file write.

## Remaining work

### Product (phase F)

- **Phase F: Optional cloud sync**: reuse archived NestJS stack (`legacy/`) for optional workspace sync.

### CI / release (operational since 14/07/2026, commit `1155d2d`)

| Workflow | Trigger | Content |
|---|---|---|
| `desktop-ci.yml` | push/PR `main`, `develop` | validate-scripts, pytest, `cargo fmt/check/test`, front lint/tests, lint-i18n, sidecar packaging (push only) |
| `desktop-release.yml` | tag `v*.*.*` | matrix 4 OS → installers + `SHA256SUMS.txt` → GitHub draft release |

**Publishing**: `./scripts/create-tag.sh` (bump version, tag, push). **Signing**: not enabled (see [signing.md](./signing.md)). **Remaining**: validate first field release on all 4 OS; harden CSP / Tauri filesystem scope.

### Functional (beyond initial release, to prioritize)

- **OCR / scanned PDFs**: Mistral OCR path exists when the active provider set supports it; Docling integration deferred. User decision ("Docling for OCR") remains open for a heavy local extractor.
- **V1→V2 storage migration** (T-V2-15b): legacy `.workproba/` under client folders not yet migrated to canonical `app_data/spaces/`.
- **Durable (Temporal/Inngest)**: deferred. Current agent loop is synchronous (one SSE turn). No long workflow resume/persistence on crash.
- **Configurable approval policy**: effect gate is always on for mapped sensitive tools; a global "auto-approve" setting is not implemented yet.
- **Office diff before write**: `preview_change` works for text/markdown; binary Office diff not yet available (T-V2-14).

### Quality / integration

- **Desktop e2e run on machine with display**: validate real chat turn in webview (streaming, sidecar badge, confirmation card, tool call rendering). Sidecar is validated live outside webview.
- **Front lint**: 1 i18n warning in `Home.vue` (`@intlify/vue-i18n/no-raw-text`).

## Local development

```bash
make dev          # recommended: sidecar + Tauri/Quasar
# or
make dev-ai       # terminal 1
make dev-desktop  # terminal 2
```

Rebuild and hot reload (front HMR, Rust recompile + window restart, Python `--reload` via `dev-ai`): see [desktop/README.md § Rebuild and hot reload](../desktop/README.md#rebuild-and-hot-reload).

## See also

- [architecture.md](./architecture.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)
- [desktop/README.md](../desktop/README.md)
- [intention.md](./intention.md)
