# Workproba Desktop

**Tauri 2** desktop shell for Workproba, targeting **macOS**, **Linux**, and **Windows**.

The UI reuses the **Quasar** front (`../front/`) in a webview. The AI core remains in **Python** (`../services/ai/`) launched as a sidecar. Rust only provides the native bridge (window, folder dialog, OS permissions, sidecar lifecycle).

## Prerequisites

| Tool | Version | Usage |
|---|---|---|
| Rust | ≥ 1.77 | Tauri shell (`src-tauri/`) |
| Node.js | ≥ 22.22 (24 recommended) | Tauri CLI + Quasar build (vitest 4 requires Node ≥ 22.22) |
| Yarn | via front | Quasar dev server on port `5053` |
| Linux OS deps | webkit2gtk, etc. | See [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) |

On Linux (Debian/Ubuntu):

```bash
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

## Development

### Single command (recommended)

From the `workproba/` root:

```bash
make dev      # or: yarn dev
```

Starts the Python sidecar, waits until it is healthy (`/health` on `127.0.0.1:8765`), then runs `tauri dev` which starts Quasar itself via `beforeDevCommand`. A single `Ctrl+C` cleanly stops both services. Sidecar logs: `tail -f .dev-ai.log` at the root.

Variants: `yarn dev:ai-only`, `yarn dev:no-ai`, `make dev-ai`, `make dev-desktop`.

### Two terminals (legacy method)

From the `workproba/` root:

```bash
make dev-ai        # Python sidecar (port 8765)
make dev-desktop   # Tauri + Quasar (port 5053)
```

Or from `desktop/`:

```bash
yarn dev
```

This command:
1. starts Quasar (`../front`, port `5053`) via `beforeDevCommand`;
2. compiles the Rust shell (`src-tauri/`, debug mode);
3. launches the Tauri window pointing at `http://localhost:5053`.

The Python AI service must be started separately in dev (see below).

### Rebuild and hot reload

`make dev-desktop` runs `tauri dev`, which includes Rust watch (no separate `cargo watch` needed).

| Modified area | Rust rebuild? | Hot reload |
|---|---|---|
| `front/` (Vue, TS, CSS) | no | yes (Quasar HMR) |
| `desktop/src-tauri/` (Rust) | yes (incremental Cargo) | no: recompiles and **restarts the window** |
| `services/ai/` (Python) | no | yes if launched via `make dev-ai` (`uvicorn --reload`) |

Useful notes:

- **First launch**: full Rust compilation, potentially long. Subsequent builds are incremental.
- **Rust**: no in-process hot reload. Tauri watches `.rs` files and relaunches the app after recompilation. Window state (open folder, etc.) is lost on restart.
- **Frontend**: the webview loads the Quasar dev server; Vue/TS changes reflect without restarting Tauri.
- **Python**: independent of `make dev-desktop`. Run `make dev-ai` in another terminal.

### Python service (dev)

```bash
cd ../services/ai && ./run_dev.sh
# or: make dev-ai (from workproba root)
```

Chat calls the Python sidecar **directly** over HTTP (`127.0.0.1:8765`), without going through Rust.

In dev, Tauri also tries to **start the sidecar automatically** (`try_spawn_dev_uvicorn`): it prefers `services/ai/.venv/bin/python -m uvicorn`, then `services/ai/.venv/bin/uvicorn`, with fallback to system `python3 -m uvicorn`. The `ai_sidecar_status` command runs a TCP liveness check on `127.0.0.1:8765` and feeds the front health badge (`useSidecarHealth`).

## Multi-platform build

```bash
yarn build
```

Configured targets: `deb`, `rpm`, `appimage`, `msi`, `nsis`, `dmg`, `app`.

Python sidecar packaging (`workproba-ai`) will be added via `externalBin` once the PyInstaller binary is ready for each triple (`x86_64-unknown-linux-gnu`, `aarch64-apple-darwin`, `x86_64-pc-windows-msvc`, etc.).

## Tauri commands exposed to the front

| Command | Role |
|---|---|
| `pick_project_folder` | Native "Open folder" dialog |
| `set_active_project_path` | Activates a folder, registers the workspace (`WorkspaceInfo`) |
| `get_active_project_path` | Returns the active folder |
| `get_workspace_data_dir` | System `.workproba` path for a folder |
| `list_workspaces` | Lists known workspaces |
| `list_conversations` / `save_conversation` | Chat sessions on disk |
| `list_documents` | Lists project files (excluding dotfiles) |
| `open_path` | Opens a file or folder with the OS default app |
| `restore_last_project_path` | Restores the last opened folder (persisted app data) |
| `start_ai_sidecar` | Starts the packaged Python binary (prod) |
| `ai_sidecar_status` | Sidecar TCP liveness (`127.0.0.1:8765`) for the front health badge |

Call from Quasar:

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
│   │   ├── commands/project.rs   # filesystem + project folder
│   │   └── sidecar.rs            # Python launch
│   ├── binaries/                 # packaged sidecars (CI build)
│   ├── capabilities/
│   └── tauri.conf.json
└── README.md
```

## See also

- [docs/desktop.md](../docs/desktop.md): full desktop architecture
- [docs/architecture.md](../docs/architecture.md): product overview
