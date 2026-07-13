# Workproba plugins

> **Last updated:** 11/07/2026

Workproba extends the agent core with a **plugin system**: agent tools, HTTP endpoints, UI slots, and namespaced storage. The sidecar registry (`services/ai/app/plugins/registry.py`) is aligned with Tauri persistence (`desktop/src-tauri/src/commands/plugins.rs`).

## Builtin plugins

| ID | Enabled by default | Role |
|---|---|---|
| `workproba.personas` | yes | Professional personas (opinion, meeting, discussion) |
| `workproba.projet` | no | Internal projects, artifact publishing |
| `workproba.browser` | no | Automated web browsing (experimental) |
| `workproba.cloud` | no | Optional cloud sync (experimental) |

Effective activation depends on user settings (`active_plugins` in Tauri settings). An enterprise preset can restrict the list (`plugins_allowed`).

## Plugin data

Each plugin stores its data under:

```
{app_data}/plugins/{plugin_id}/
```

Personas example:

```
{app_data}/plugins/workproba.personas/
├── sets.json
├── meetings/{meeting_id}/transcript.json
└── discussions/{discussion_id}/messages.json
```

## UI integration

| Slot | Key files | Usage |
|---|---|---|
| Right panel | `RightPanel.vue` | Personas tab, dynamic plugin tabs (`usePluginSlots`) |
| Chat composer | `ChatView.vue` | "+" menu: attachments + personas actions |
| Side chat | `SideChatPanel.vue`, `PersonasSideChat.vue` | Discussion / opinion in side panel (`Ctrl+Shift+L`) |
| Shared actions | `usePersonasActions.ts` | Switch to a chat session then trigger the action |

Useful shortcuts: `Ctrl+B` (right panel), `Ctrl+Shift+L` (side chat).

## Personas plugin (`workproba.personas`)

### Concept

Simulate **complementary professional perspectives** on a topic: HR, legal, CFO, engineer, etc. The builtin **Improba** set (`id: default`) is provided in code and is not editable. Custom sets can be created via the API.

### Limits

| Parameter | Value |
|---|---|
| Max personas per session | 5 |
| Max meeting rounds | 5 |
| Default meeting rounds | 3 |

### Modes

| Mode | SSE endpoint | Description |
|---|---|---|
| Opinion | `POST /plugins/personas/ask` | Each persona gives their opinion |
| Meeting | `POST /plugins/personas/meeting` | Multi-turn simulation |
| Discussion | `POST /plugins/personas/discuss` | Guided multi-persona exchange |

Optional parameter `include_memory` + `workspace_data_dir`: enriches context via project memory search (`search_combined`).

### Agent tools

If the plugin is active: `ask_personas`, `simulate_meeting`.

### CRUD endpoints

| Method | Route |
|---|---|
| GET/POST | `/plugins/personas/sets` |
| DELETE | `/plugins/personas/sets/{set_id}` |
| GET | `/plugins/personas/meetings`, `/plugins/personas/meetings/{id}` |
| GET | `/plugins/personas/discussions`, `/plugins/personas/discussions/{id}` |
| POST | `/plugins/personas/estimate-cost` |

### Typical UX flow

1. **From the composer**: "+" menu → personas action → switch to a chat session → `ChatPage` runs the action via `usePersonasNavigation`.
2. **From the right panel**: Personas tab → choose set and action → `usePersonasActions` handles navigation.
3. **Resume**: meeting/discussion identifiers stored in `sessionStorage` to relaunch or resume.

## Project plugin (`workproba.projet`)

Internal project management and artifact publishing from the explorer or document preview.

Main endpoints: `/plugins/projet/projects`, `/plugins/projet/publish`, `/plugins/projet/artefacts`.

## Experimental plugins

- **Browser**: `/plugins/browser/navigate`, `/snapshot`, `/action`, `/close`, `/status`
- **Cloud**: `/plugins/cloud/status`, `/config`, `/sync`

Disabled by default; reserved for dev and advanced presets.

## See also

- [memory.md](./memory.md): scoped memory (used by personas with `include_memory`)
- [architecture.md](./architecture.md): UI shell (sidebar, right panel)
- [services/ai/README.md](../services/ai/README.md): full endpoint catalog
