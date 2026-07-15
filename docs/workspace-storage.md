# Space storage (espace)

> **Last updated:** 15/07/2026  
> **Terminology:** UI label **space** / FR **espace**; internal identifiers may still use `workspace_id` in code and `registry.json`.

## Terminology

| Term | Meaning |
|---|---|
| **Space** | User-facing concept: one local folder on disk that the user works in. The UI says "Open a space". |
| **Display title** | Renameable label shown in the sidebar (default = folder basename). Updated via `update_workspace_title`. |
| `workspace_id` / `ws_…` | Stable internal identifier in code and `registry.json`. Unchanged if the folder is renamed or the display title is edited. |
| `folder_path` | Current absolute path to the space's folder on disk (updated on each open). |
| **Project memory** (`project` scope in sidecar) | Per-space RAG and explicit memories in `.workproba/memory.db`. Not the `workproba.projet` plugin. |
| `registry.json` → `workspaces` array | Internal registry field name (unchanged). Each entry maps a `workspace_id` to folder path and display title. |

On disk, metadata lives under `{app_data}/spaces/` (migrated from legacy `{app_data}/workspaces/` on first launch after the Space UX update).

## Principle

A **space** = a user folder on disk (e.g. `~/Clients/Dupont_2026/`).

**Business files** stay in that folder, untouched. **Workproba metadata** (conversations, versions, per-space RAG memory and project memories) lives in a dedicated application directory, **not** in the client folder. Some data is **global user** data (user memory, profile, plugins).

This model follows **Claude Cowork** (metadata in Application Support, user files in place) and avoids **Cursor** pitfalls (path hash → lost history on rename).

## Layout

```
# User files (unchanged)
~/Clients/Dupont_2026/
├── Rapport.docx
└── Tableau_CA.xlsx

# Workproba metadata (system folder)
~/.local/share/fr.improba.workproba/          # Linux
~/Library/Application Support/fr.improba.workproba/   # macOS
%LOCALAPPDATA%/fr.improba.workproba/          # Windows
├── registry.json                           # index of known spaces (internal key: workspaces[])
├── last-project.json                       # last opened space
├── settings.json                           # app settings (LLM providers, active plugins)
├── user/
│   └── memory.db                           # global explicit memories (user scope)
├── plugins/
│   └── workproba.personas/                 # plugin data (sets, meetings, discussions)
├── audit/
│   ├── audit.jsonl                         # local audit log
│   └── config.json                         # retention, activation
└── spaces/
    └── ws_a1b2c3d4.../
        └── .workproba/
            ├── manifest.json               # folder path, display title, dates
            ├── config.json                 # project instructions (later phase)
            ├── conversations/
            │   └── sess_....json           # one session = one JSON file
            ├── versions/                   # snapshots before AI modification
            ├── attachments/                # chat attachments per session
            └── memory.db                   # per-space RAG + explicit memories (project scope)
```

## Display title

Each space has a **display title** shown in the sidebar (default = folder basename). The user can rename it without affecting the folder on disk or the stable `workspace_id`. Tauri command: `update_workspace_title(workspace_id, title)` → updates `manifest.json` and the `registry.json` entry.

## Migration from `workspaces/`

On first launch after the Space UX update, if `{app_data}/workspaces/` exists and `{app_data}/spaces/` does not, Tauri **renames** `workspaces/` → `spaces/` automatically. No data loss; IDs and registry entries are preserved.

## Stable identification

| Field | Role |
|---|---|
| `workspace_id` | Stable UUID (`ws_…`), unchanged if the folder is renamed or the display title is edited |
| `folder_path` | Current folder path (updated on each open) |
| `folder_path_normalized` | Canonical path to find the space after partial rename |

On space open: lookup by canonical path → reuse existing ID or create a new space.

## Responsibility split

| Data | Location | Access |
|---|---|---|
| Office/PDF documents | User folder | Tauri (list, open) + Python (read/write) |
| Conversations | `.workproba/conversations/` (system) | Tauri → Quasar front |
| File versions | `.workproba/versions/` (system) | Python sidecar |
| Chat attachments | `.workproba/attachments/` (system) | Python sidecar |
| Per-space memory (RAG + explicit) | `.workproba/memory.db` (system) | Python sidecar |
| User memory (explicit) | `{app_data}/user/memory.db` | Python sidecar |
| Plugin data | `{app_data}/plugins/{plugin_id}/` | Python sidecar + Tauri settings |
| Audit log | `{app_data}/audit/` | Python sidecar |
| Space registry | `registry.json` | Tauri |

The Python sidecar receives `workspace_data_dir` in agent and memory payloads to write to the right place. See [memory.md](./memory.md) for scope details.

## Session schema (`conversations/sess_….json`)

One session = one JSON file, read/written via Tauri commands
(`list_conversations`, `get_conversation`, `save_conversation`).

| Field | Role |
|---|---|
| `id` | Session identifier (`sess_…`) |
| `title` | Display title (auto, first question) |
| `messages` | Message list (roles `user`/`assistant`, ordered `parts` text/reasoning/tool) |
| `reasoningEffort` | Reasoning level chosen for the conversation (`none`/`low`/`medium`/`high`) |
| `model` | LLM model chosen for the conversation (overrides provider default) |
| `summary` | Optional auto-generated cross-session digest (used by promotion and `recall_project_sessions`) |
| `createdAt` / `updatedAt` | Timestamps |

`reasoningEffort` and `model` are **persisted per session**: restored on open if still applicable to the active provider set, otherwise fallback to the set default model. On session switch, overrides are cleared before load completes. Values incompatible with the model catalogue (e.g. `medium` on Mistral medium) are clamped at send time. See [provider-sets-reasoning.md](./provider-sets-reasoning.md).

Persistence is **debounced** and atomic
(`persistSession` saves `messages` + `reasoningEffort` + `model` in a single
write) to avoid races during streaming. `model` is optional
(`#[serde(default, skip_serializing_if)]`) to remain readable by older versions.

See also [architecture.md § Model and reasoning per conversation](./architecture.md#model-and-reasoning-per-conversation) and [provider-sets-reasoning.md](./provider-sets-reasoning.md).

## Initial release migration

Sessions stored in `localStorage` (`workproba:sessions:{path}`) are **imported automatically** on first access to a space, then removed from the browser.

## Competitive comparison

| Tool | User files | App metadata |
|---|---|---|
| **Claude Cowork** | Local folder mounted as-is | `Application Support/Claude-3p/` |
| **Cursor** | `.cursor/` = config only | `workspaceStorage/{hash}/` (fragile on move) |
| **Workproba** | Client folder without pollution | `{app_data}/spaces/{uuid}/.workproba/` |

## See also

- [desktop.md](./desktop.md)
- [architecture.md](./architecture.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)
