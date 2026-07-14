# Workproba

AI is fragmenting: a copilot in every app, contexts that never overlap, features siloed inside each suite. Our conviction is that it should first be **a personal work interface**, centered on the person, connected to their folders and tools, rather than embedded in each one of them.

**Workproba** is a desktop application (**macOS, Linux, Windows**) that embodies this principle. You **open a space** (a local folder on your machine); the assistant works directly on your files (Word, Excel, PDF), indexes and remembers context locally, and relies on the **LLM provider of your choice** (Ollama, Mistral, OpenAI, etc.). Your documents and memory stay on the machine; relevant context is sent to the model on each exchange, according to your configuration.

*Local-first desktop app. Local files and memory, configurable LLM providers.*

## Preview

| Light mode | Dark mode |
|---|---|
| ![Workproba in light mode, chat, personas and workspace](./docs/images/workproba-light-mode.jpg) | ![Workproba in dark mode, chat, files and workspace](./docs/images/workproba-dark-mode.jpg) |

## Features

- **Agent chat**: SSE streaming, model and reasoning per conversation, attachments, composite "+" menu
- **Scoped memory**: global user memories + project memories, local RAG, agent `remember` tool
- **Personas plugin**: professional perspectives, simulated meetings, discussions (Improba builtin set)
- **Spaces**: spaces/conversations sidebar (renameable titles), right panel (files, preview, personas), side chat
- **Documents**: HTML/text preview via sidecar, images via Tauri protocol-asset, versions before write
- **Plugins**: project, browser, cloud (extensible, activatable in settings)

## License

Workproba is distributed under a **dual license**: free personal and educational use ([WPEL](./LICENSE)), commercial license for enterprise and institutional use.

See [LICENSING.md](./LICENSING.md) for the full guide, FAQ, and contacts.

## First-time installation

Download the installer for your system (Windows, macOS, or Linux) from the repository **Releases** page. Installers are not yet digitally signed: Windows and macOS show a security warning on first launch. This is expected.

Step-by-step guide (SmartScreen, Gatekeeper, `.deb`, AppImage, uninstall): **[docs/installateurs.md](./docs/installateurs.md)**.

## Documentation

- [docs/installateurs.md](./docs/installateurs.md): installation (end users)
- [docs/intention.md](./docs/intention.md): product framing
- [docs/desktop.md](./docs/desktop.md): desktop architecture
- [docs/architecture.md](./docs/architecture.md): technical overview
- [docs/memory.md](./docs/memory.md): user/project memory and RAG
- [docs/plugins.md](./docs/plugins.md): plugins (personas, project, …)
- [docs/workspace-storage.md](./docs/workspace-storage.md): per-space storage
- [docs/README.md](./docs/README.md): full documentation index
- [desktop/README.md](./desktop/README.md): Tauri development
- [services/ai/README.md](./services/ai/README.md): Python sidecar API

## Structure

```
workproba/
├── desktop/          # Tauri shell (product)
├── front/            # Quasar UI (webview)
├── services/ai/      # Python AI sidecar
├── docs/
├── scripts/
└── legacy/           # Former web stack (archived, unused)
```

## Getting started

### Prerequisites

- Rust ≥ 1.77, Node.js ≥ 22.22 (24 recommended for vitest 4 / Quasar build), Yarn
- Python 3.12 + uvicorn
- Tauri OS dependencies: see [desktop/README.md](./desktop/README.md)

### Development

#### Single command (recommended)

Starts the Python sidecar, waits until it is healthy (`/health`), then launches Tauri which starts Quasar itself. A single `Ctrl+C` cleanly stops both.

```bash
make dev          # or: yarn dev
```

Variants:

```bash
make dev-ai       # Python sidecar only
make dev-desktop  # Tauri only (if sidecar already running elsewhere)
yarn dev:no-ai    # desktop without (re)starting the sidecar
yarn dev:ai-only  # Python sidecar only
```

Useful environment variables:

| Variable | Default | Role |
|---|---|---|
| `AI_PORT` | `8765` | Python sidecar port |
| `AI_HOST` | `127.0.0.1` | Sidecar host |
| `HEALTH_TIMEOUT_S` | `30` | Max wait for `/health` |
| `AI_SKIP_WAIT` | `0` | `=1` to skip sidecar health wait |

Sidecar logs: `tail -f .dev-ai.log` at the repository root.

#### Two terminals (legacy method)

```bash
# Terminal 1: Python sidecar (:8765)
make dev-ai

# Terminal 2: Tauri + Quasar (:5053)
make dev-desktop
```

Or: `bash scripts/dev.sh` then `cd desktop && yarn dev`

### Build installer

```bash
make build-desktop    # PyInstaller sidecar + Tauri installers
```

Publish a release: `./scripts/create-tag.sh` (creates tag `vX.Y.Z`, triggers GitHub Actions). Installers are unsigned for now; see [docs/signing.md](./docs/signing.md).

## CI / CD

| Workflow | Trigger | Role |
|---|---|---|
| `desktop-ci.yml` | push/PR `main`, `develop` | validate-scripts, pytest, Rust, front lint/tests, lint-i18n, sidecar packaging |
| `desktop-release.yml` | tag `v*.*.*` | 4-OS installers + `SHA256SUMS.txt`, draft GitHub release |

Pipeline shipped **14/07/2026** (commit `1155d2d`). Remaining: first tagged release validated in the field, installer signing ([docs/signing.md](./docs/signing.md)).
