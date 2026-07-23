# Workproba Desktop (application locale)

> **Status:** Product decision: desktop pivot  
> **Last updated:** 20/07/2026  
> **Terminology:** user-facing **space** (FR: **espace**) = one local folder you work in

## Decision

Workproba becomes a **desktop application** (Claude Cowork style) working on local folders, connected to **Workproba Cloud** (Improba Cloud Mode A) for managed capabilities (standard path). Multi-platform:

| OS | Target formats |
|---|---|
| macOS | `.app`, `.dmg` |
| Linux | `.deb`, `.rpm`, `.AppImage` |
| Windows | `.msi`, `.exe` (NSIS) |

Chosen technology: **Tauri 2** (lightweight Rust shell + system webview + existing Quasar UI).

The AI agent remains in **Python** (sidecar). Rust does not replace Python: it provides the native bridge (filesystem, window, permissions, packaging).

## Product metaphor (non-coders)

The user **opens a space** (a local folder on disk). The Imp (agent) works inside it:

- reads and modifies Word, Excel, PDF via **fixed agent tools** (python-docx, openpyxl, etc.);
- does **not** execute arbitrary user- or model-generated code in V2 (`run_code` dormant);
- relies on **memory** indexed from folder documents.

Main UI concepts:

| Displayed concept | Meaning |
|---|---|
| **Space** | A local folder the user works in (display title renameable in sidebar) |
| **Conversation** | Exchange with the Imp |
| **Memory** | What the tool knows about the space (per-space RAG + user/project memories) |
| **Regards métier** | Simulated professional perspectives (plugin `workproba.personas`: opinion, crossed perspectives, discussion) |
| **Capacités** | Activatable integrated features (hub in titlebar, **delivered V2.2 PR 2–3**); technical plugins under the hood |

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
│  agent · RAG · fixed tools │    └──────────────┬──────────────┘
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

Workproba metadata lives in the **application folder**, not in the client folder. See [space storage](./workspace-storage.md) (espace).

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
5. Python runs the agent loop: LLM, fixed file/Office tools, local search (`run_code` not exposed in V2).
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
| AI core | Python / FastAPI | Agent loop, extraction, RAG, fixed tool implementations |
| Local data | `{app_data}/spaces/{id}/.workproba/` | Sessions, versions, memory |
| Cloud legacy (archived) | `legacy/` | Former NestJS stack |
| Improba Cloud (Mode A MVP) | `workproba-cloud/` | Auth user + DeviceBearer side-car, managed capabilities (API connectors), transport relay |

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
| **C** | Done | Direct Python SSE, `LocalProjectClient`, fixed agent tools (`run_code` not exposed in V2) |
| **D** | Done | SQLite RAG, Office extraction, sidecar monitoring |
| **D+** | Done | Scoped user/project memory, builtin plugins (Regards métier), attachments, document preview, audit, Human Approval Gate, Work Event Bus |
| **E** | Done | Multi-OS packaging + PyInstaller sidecar (`scripts/build-sidecar.sh`, CI `desktop-release.yml`) |
| **F** | **Partial / MVP Mode A** | Improba Cloud (`workproba-cloud/`): desktop login (`POST /devices/login` → `desktop-bearer` → durable `wp_dev_*`), join via `join_token`, first-run onboarding (`EngineOnboardingWizard`), managed capabilities under **Workproba Cloud** (`echo`, `ihora.shaped` stub, `ihora` HTTP allowlist org, **15 tools** incl. `list_users`), dedicated agent tools + `invoke_managed_connector`, **per-space** `capabilities.json`, CloudPanel, sync published artefacts, Capabilities hub hierarchy (21/07), PPTX visual pipeline (HTML + Chromium fallback) |

### Phase D: validation

- **Sidecar (Python)**: streaming chat, fixed file/Office tools, RAG, scoped memory, builtin plugins, managed connectors, per-space capabilities, work events, effect gate. pytest: **~900+ tests** collected (see [testing.md](./testing.md)).
- **Rust shell**: venv-aware sidecar spawn + `ai_sidecar_status` + `protocol-asset` for image preview. `cargo check` OK.
- **Front**: `WorkprobaLayout` (sidebar, right panel, side chat, Capabilities drawer), `useSidecarHealth`, Regards chip in composer (**V2.2 PR 3**).
- **End-to-end desktop run**: `make dev`, open a space, test chat, memory, personas, document preview, confirmation on file write.

## Remaining work

### Product (phase F)

**Livré (MVP Mode A, 20–23/07/2026)** :

- Desktop cloud login (`CloudLoginModal` → `POST /devices/login` → sidecar exchange → DeviceBearer `wp_dev_*` durable after sleep/wake)
- First-run onboarding (`EngineOnboardingWizard`: engine choice, cloud login/register, Mistral key, manual OpenAI-compat)
- Join device (`POST /devices/join` via `join_token`; `device_code` → `join_token_required`; pasting an existing bearer still works)
- Capacités managées (API `connectors`) : `echo`, `ihora.shaped` (stub), `ihora` (HTTP réel, **15 tools** dont `list_users`, allowlist org) via `GET /connectors` (`catalogVersion`), `POST /connectors/:id/invoke` ; invoke sans `subject_id` / `org_id` côté client
- Desktop : `RemoteCapabilityGateway`, outils agent dédiés `managed_*` + `invoke_managed_connector`, sidecar `GET /plugins/cloud/connectors`, freeze allowlist par tour
- **Hub Capacités (21/07)** : **Workproba Cloud** en premier ; zone **Sous-capacités** dépliante (Gestion de projet + managées type Ihora, cartes compactes) ; stubs masqués en guidé
- **Capacités par espace (22/07)** : `capabilities.json`, `SpaceCapabilitiesPanel`, `GET`/`PUT /workspace/capabilities`
- CloudPanel (join, capacités managées, regards, projets), sync artefacts publiés, org LLM (DeviceBearer) ; quota illimité sans ligne `llm_quota_limit`
- Secrets org + overrides user connecteurs : persistés PostgreSQL (+ AES-GCM pour secrets) ; UI admin org allowlist/secrets/overrides
- PPTX : builder natif éditable + pipeline HTML/Chromium (`pptx_svg`) avec repli

**Ouvert** : SSO Microsoft, Mode B deploy, smoke E2E HTTP, presets connecteurs complets.

Monorepo `workproba-cloud/` (NestJS + Quasar admin). Plugin desktop `workproba.cloud` via `CloudControlPlaneClient` et `RemoteCapabilityGateway`. Agent loop stays on desktop. Pas de réactivation de `legacy/api/` (`agent-gateway`). Spec : [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md).

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
- **Office preview before write**: `POST /documents/preview-change` builds proposed Office bytes (docx/xlsx/pdf/pptx) and shows HTML preview before approval (PPTX uses the HTML slides pipeline when available). Pixel-perfect binary diff is not available (T-V2-14 partially addressed).
- **Per-space capabilities**: see [capacites.md](./capacites.md) and [architecture.md](./architecture.md#per-space-capabilities-profile).

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
