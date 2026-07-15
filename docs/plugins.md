# Workproba plugins

> **Last updated:** 15/07/2026 (V2.2 PR 1–3)

Workproba extends the agent core with a **plugin system** (technical layer): agent tools, HTTP endpoints, UI slots, and namespaced storage. User-facing discovery uses **activatable capabilities** (hub « Capacités », V2.2) — see [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md).

## Implementation status (honest)

| Layer | Role | Local plugin runtime |
|---|---|---|
| Tauri (`desktop/src-tauri/src/commands/plugins.rs`) | Persistence, activation, local folder copy | Install + registry only |
| Sidecar (`services/ai/app/plugins/registry.py`) | Agent tools for **builtin IDs only** | Not loaded |
| Front (`front/src/plugins/pluginSlotComponents.ts`) | Static Vue component map | Not loaded |

Only **`right_panel`** and **`side_chat`** slots are generalized via `usePluginSlots.ts`. Other slots (`composer_actions`, etc.) are wired manually for builtins.

## Builtin plugins

| ID | Enabled by default | Capability (guided UI) | Primary surface |
|---|---|---|---|
| `workproba.personas` | yes | Regards métier | Side chat; central view for crossed perspectives |
| `workproba.projet` | no | Projets et livrables | Right panel, Project tab |
| `workproba.browser` | no | Navigation web | Right panel, Browser tab |
| `workproba.cloud` | no | Synchronisation (under Projects) | Nested under Project — not a top-level tab |

Effective activation depends on Tauri settings (`active_plugins`). Enterprise presets can restrict the list (`plugins_allowed`).

## Plugin data

Each plugin stores its data under:

```
{app_data}/plugins/{plugin_id}/
```

Project plugin example (structured, not a single `data.json`):

```
{app_data}/plugins/workproba.projet/
├── projects.json
└── artefacts/{project_id}/...
```

Personas example:

```
{app_data}/plugins/workproba.personas/
├── sets.json
├── meetings/{meeting_id}/transcript.json
└── discussions/{discussion_id}/messages.json
```

## UI integration

| Slot | Status | Key files | Usage |
|---|---|---|---|
| Right panel | **Generalized** | `RightPanel.vue`, `usePluginSlots` | Active plugin tabs only (Project, Browser when enabled) — **no ghost tabs** for disabled modules |
| Side chat | **Generalized** | `SideChatPanel.vue`, `PersonasSideChat.vue` | Regards métier opinion/discussion (`Ctrl+Shift+L`) |
| Chat composer | Manual | `ChatView.vue` | `+` menu: attachments only ; chip **Regards** (three usages) when personas active |
| Capabilities hub | **Delivered V2.2** | `CapabilitiesButton.vue`, `CapabilitiesDrawer.vue`, `useCapabilities.ts` | Titlebar drawer: discover, activate, open home surface |
| Settings | Static | `PluginsPanel.vue` | Advanced mode: **Extensions** (technical details) |

Useful shortcuts: `Ctrl+B` (right panel), `Ctrl+Shift+L` (side chat).

## Regards métier (`workproba.personas`)

### Concept

Simulate **complementary professional perspectives** (HR, legal, CFO, engineer, etc.). Guided UI vocabulary: « Regards métier », « Demander un avis », « Croiser plusieurs regards » — not « Personas » or « Consult experts ».

### Surfaces

- **Opinion / discussion**: side chat panel (not a generic right-panel Personas tab).
- **Crossed perspectives (meeting)**: dedicated central full-screen view.

See [personas-ui.md](../../workproba-improba/roadmaps/personas-ui.md).

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
| Meeting | `POST /plugins/personas/meeting` | Multi-turn simulation (central view) |
| Discussion | `POST /plugins/personas/discuss` | Guided multi-persona exchange (side chat) |

### Agent tools

If active: `ask_personas`, `simulate_meeting`.

## Project plugin (`workproba.projet`)

Internal project management and artifact publishing. Disabled by default; discoverable via Capabilities hub. Contextual hint in document preview opens the hub (focus Projects). Publishing requires Human Approval Gate (`effect: publish`).

Main endpoints: `/plugins/projet/projects`, `/plugins/projet/publish`, `/plugins/projet/artefacts`.

## Experimental plugins

- **Browser**: see [browser.md](./browser.md)
- **Cloud plugin** (`workproba.cloud`): local mount sync via **`ProjectSyncPort`** and `project:sync` permission (PR 4). V3: plan de contrôle SaaS via `workproba-cloud/` — see [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md). No direct project namespace access. Bidirectional sync deferred to V3.

## Local plugins

Tauri can copy and register a local plugin folder. **Runtime loading (Python tools + Vue components) is not implemented in V2.** Hidden in production builds unless `VITE_LOCAL_PLUGIN_INSTALL=true` (dev builds always allow install).

## See also

- [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md): capabilities UX plan
- [contrat-plugin.md](../../workproba-improba/roadmaps/contrat-plugin.md): contract + implementation matrix
- [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md): control plane V3
- [memory.md](./memory.md): scoped memory
- [architecture.md](./architecture.md): UI shell
- [services/ai/README.md](../services/ai/README.md): endpoint catalog
