# Workproba memory

> **Last updated:** 11/07/2026

Workproba combines two complementary mechanisms:

1. **Project RAG**: vector index of folder documents (semantic search).
2. **Explicit memories**: facts memorized voluntarily, by the user or the agent.

Explicit memories exist at **two scopes**; RAG remains attached to the **project** (workspace).

## Scopes

| Scope | Range | SQLite file | Typical usage |
|---|---|---|---|
| `user` | Global, shared across all workspaces | `{app_data}/user/memory.db` | Preferences, personal context, habits |
| `project` | One workspace | `{workspace_data_dir}/memory.db` | Client folder business facts, project decisions |

`{app_data}` = Workproba application folder (`~/.local/share/fr.improba.workproba/` on Linux, etc.).
`{workspace_data_dir}` = `{app_data}/workspaces/{workspace_id}/.workproba/`.

Path resolution is centralized in `services/ai/app/memory_stores.py`.

## RAG vs explicit memories

On the **project** scope, both coexist in the same `memory.db` base:

- **RAG**: document chunks indexed via `/agent/index-workspace` or during agent reads. Vector search (sqlite-vec) or substring fallback if embeddings are disabled.
- **Explicit memories**: text entries added manually (UI) or via the agent `remember` tool. Recorded source: `manual` or `agent`.

On the **user** scope, only explicit memories are stored (no RAG indexing of folders).

## Agent injection

On each turn, the `memory_prompt` tool (`services/ai/app/agent/tools.py`) injects recent explicit memories into the system prompt:

- up to 64 **user** entries;
- up to 64 **project** entries.

The agent can also memorize via the `remember(content, scope="user"|"project")` tool (default: `project`).

## REST API (sidecar)

All memory endpoints require the `X-Internal-Secret` header (loopback only).

| Method | Route | Role |
|---|---|---|
| GET | `/memory/items?workspace_data_dir=&memory_scope=user\|project` | List explicit memories |
| GET | `/memory/search?query=&memory_scope=user\|project\|all` | Search (project = RAG + explicit; user = explicit only) |
| POST | `/memory/add` | Manual add (`content`, `memory_scope`) |
| POST | `/memory/forget` | Delete by `memory_id` |
| DELETE | `/memory` | Wipe (`scope`: `all` / `memories` / `conversations`; `confirmed: true`) |

The front calls these routes via `front/src/services/aiSidecar.ts` and the `useMemory.ts` composable.

## User interface

The **Memory** panel (`MemoryPanel.vue`) opens from the sidebar (brain icon, `WorkspaceSidebar.vue`).

Features:

- **User** / **Project** tabs;
- manual memory add;
- search in the active scope;
- delete an entry.

## See also

- [workspace-storage.md](./workspace-storage.md): on-disk layout
- [architecture.md](./architecture.md): overview
- [services/ai/README.md](../services/ai/README.md): sidecar API catalog
