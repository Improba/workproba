# Per-workspace storage

> **Last updated:** 11/07/2026

## Principle

A **workspace** = a user folder on disk (e.g. `~/Clients/Dupont_2026/`).

**Business files** stay in that folder, untouched. **Workproba metadata** (conversations, versions, project RAG memory and project memories) lives in a dedicated application directory, **not** in the client folder. Some data is **global user** data (user memory, profile, plugins).

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
├── registry.json                           # index of known workspaces
├── last-project.json                       # last opened folder
├── settings.json                           # app settings (LLM providers, active plugins)
├── user/
│   └── memory.db                           # global explicit memories (user scope)
├── plugins/
│   └── workproba.personas/                 # plugin data (sets, meetings, discussions)
├── audit/
│   ├── audit.jsonl                         # local audit log
│   └── config.json                         # retention, activation
└── workspaces/
    └── ws_a1b2c3d4.../
        └── .workproba/
            ├── manifest.json               # folder path, title, dates
            ├── config.json                 # project instructions (later phase)
            ├── conversations/
            │   └── sess_....json           # one session = one JSON file
            ├── versions/                   # snapshots before AI modification
            ├── attachments/                # chat attachments per session
            └── memory.db                   # project RAG + explicit memories (project scope)
```

## Stable identification

| Field | Role |
|---|---|
| `workspace_id` | Stable UUID (`ws_…`), unchanged if the folder is renamed |
| `folder_path` | Current folder path (updated on each open) |
| `folder_path_normalized` | Canonical path to find the workspace after partial rename |

On folder open: lookup by canonical path → reuse existing ID or create a new workspace.

## Responsibility split

| Data | Location | Access |
|---|---|---|
| Office/PDF documents | User folder | Tauri (list, open) + Python (read/write) |
| Conversations | `.workproba/conversations/` (system) | Tauri → Quasar front |
| File versions | `.workproba/versions/` (system) | Python sidecar |
| Chat attachments | `.workproba/attachments/` (system) | Python sidecar |
| Project memory (RAG + explicit) | `.workproba/memory.db` (system) | Python sidecar |
| User memory (explicit) | `{app_data}/user/memory.db` | Python sidecar |
| Plugin data | `{app_data}/plugins/{plugin_id}/` | Python sidecar + Tauri settings |
| Audit log | `{app_data}/audit/` | Python sidecar |
| Project registry | `registry.json` | Tauri |

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

`reasoningEffort` and `model` are **persisted per session**: restored on open if still applicable to the active provider, otherwise fallback to the provider default model. Persistence is **debounced** and atomic
(`persistSession` saves `messages` + `reasoningEffort` + `model` in a single
write) to avoid races during streaming. `model` is optional
(`#[serde(default, skip_serializing_if)]`) to remain readable by older versions.

See also [architecture.md § Model and reasoning per conversation](./architecture.md#model-and-reasoning-per-conversation).

## Initial release migration

Sessions stored in `localStorage` (`workproba:sessions:{path}`) are **imported automatically** on first access to a workspace, then removed from the browser.

## Competitive comparison

| Tool | User files | App metadata |
|---|---|---|
| **Claude Cowork** | Local folder mounted as-is | `Application Support/Claude-3p/` |
| **Cursor** | `.cursor/` = config only | `workspaceStorage/{hash}/` (fragile on move) |
| **Workproba** | Client folder without pollution | `{app_data}/workspaces/{uuid}/.workproba/` |

## See also

- [desktop.md](./desktop.md)
- [architecture.md](./architecture.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)
