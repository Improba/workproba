# Workproba plugins

> **Last updated:** 15/08/2026 (bundled Chromium, Capabilities via organization environment)

Workproba extends the agent core with a **plugin system** (technical layer): agent tools, HTTP endpoints, UI slots, and namespaced storage. User-facing discovery uses **activatable capabilities** (organization environment → **Configure capabilities**, V2.2) — see [capacites.md](./capacites.md) and [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md).

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
| `workproba.cloud` | no | Workproba Cloud | CloudPanel : join, connecteurs, regards, projets |

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
├── managed/{catalog_id}/{version}/catalog.json
├── managed/state.json
├── meetings/{meeting_id}/transcript.json
└── discussions/{discussion_id}/messages.json
```

## UI integration

| Slot | Status | Key files | Usage |
|---|---|---|---|
| Right panel | **Generalized** | `RightPanel.vue`, `usePluginSlots` | Active plugin tabs only (Project, Browser when enabled) — **no ghost tabs** for disabled modules |
| Side chat | **Generalized** | `SideChatPanel.vue`, `PersonasSideChat.vue` | Regards métier opinion/discussion (`Ctrl+Shift+L`) |
| Chat composer | Manual | `ChatView.vue` | `+` menu: attachments only ; chip **Regards** (three usages) when personas active |
| Capabilities hub | **Delivered V2.2** | `EnvironmentDrawer.vue`, `CapabilitiesDrawer.vue`, `useCapabilities.ts` | Organization environment → **Configure capabilities**; builtin plugins are not toggled in Settings → Extensions |
| Settings | Static | `PluginsPanel.vue` | Advanced mode: **Extensions** (technical details) |

Useful shortcuts: `Ctrl+B` (right panel), `Ctrl+Shift+L` (side chat).

## Regards métier (`workproba.personas`)

### Concept

Simulate **complementary professional perspectives** (HR, legal, CFO, engineer, etc.) — product vocabulary: **Agent métier** (object), **Regard** (read-only consultative mode). Guided UI: « Regards métier », « Demander un avis », « Croiser plusieurs regards » — not « Personas » or « Consult experts ».

**Sources:** builtin integrated set; **org catalogs** published on Workproba Cloud (`specialists[]` in signed `RegardEnterprise`, synced manually via CloudPanel → `POST /plugins/cloud/sync-regards`). Dual-read legacy `personas[]` in catalog payloads.

LLM calls use the same **active provider set** as chat. With **Improba Cloud** (`device_bearer`), personas SSE endpoints receive `provider_set` + `cloud_plugin_data_dir`; the front runs `initCloud()` before launch (fail-closed on readiness errors).

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

The main assistant (**Imp**) delegates to an org agent via **`summon_specialist`** (not direct `managed_*` / `invoke_managed_connector` on the parent turn). Runs a bounded **SpecialistRun** (`specialist_run.py`) with doctrine + tool allowlist from the catalog.

**Streaming (06/08/2026):** SpecialistRun uses **`agent.iter`** (not a blocking `agent.run`). Nested model tokens, thinking, and tool events are forwarded on the parent `/agent/turn` SSE via `ToolDeps.event_queue`, scoped with **`parent_tool_call_id`** = the `summon_specialist` tool call id. Front: compact inline **handoff card** (`SpecialistHandoffCard`, rehydrated on reload) ; thinking, nested tools, and the specialist answer stay behind **« Voir le détail »** by default. The card is inserted **at the `summon_specialist` position** in the message flow (`insertPerspectiveCardsInBlocks`) so Imp’s follow-up text appears **below** the card. Human Approval Gate when the specialist invokes a write/external tool ; nested managed confirmations without a parent tool row use an **orphan `ConfirmationCard`** on the assistant message.

### ManagedAgentsPort (enterprise catalogs)

> **Alias produit :** `ManagedAgentsPort`. **Code actuel :** `ManagedRegardsPort` jusqu'au renommage.

Enterprise agents catalogs are installed in the **personas plugin namespace only**. The cloud plugin never reads `workproba.personas/` directly; it calls the typed port with permission `regards:managed`.

| Operation | HTTP (sidecar) | Storage |
|---|---|---|
| List installed catalogs | `GET /plugins/personas/managed` | `managed/{catalog_id}/{version}/` |
| Install signed bundle | `POST /plugins/personas/managed/install` | verifies Ed25519 or HMAC-SHA256 |
| Activate catalog | `POST /plugins/personas/managed/{id}/activate` | `managed/state.json` |
| Remove revoked version | `DELETE /plugins/personas/managed/{id}/{version}` | deletes version dir |

Active managed catalogs appear in `GET /plugins/personas/sets` with `provenance: "managed"` (UI badge: administré). Builtin set uses `integrated`; custom sets use `personal`. Catalog entries expose `specialists[]` (preferred) or legacy `personas[]`.

See [plan.md](./plan.md) for the full agents métier / Regard product model and phasing.

## Project plugin (`workproba.projet`)

Internal project management and artifact publishing. Disabled by default; discoverable via Capabilities hub. Contextual hint in document preview opens the hub (focus Projects). Publishing requires Human Approval Gate (`effect: publish`).

**Product model (sources of truth):** **solo project** = local SoT (`{app_data}/plugins/workproba.projet/`, list/publish/open local). **Shared project** = cloud SoT (control plane list/publish/open/republish + S3 blobs) ; local storage is a **disposable cache** only (pull/open on demand). **Mount sync** (`ProjectSyncPort`) = technical NAS bridge, not a shared project ; mirror push/pull is a **deprecated product path** and **blocked when enrolled** (agent tools + HTTP `/plugins/cloud/sync`, `/pull`). Bidirectional sync and conflicts are **out of scope**.

Main endpoints: `/plugins/projet/projects`, `/plugins/projet/publish`, `/plugins/projet/artefacts`.

## Improba Cloud / Workproba Cloud (Mode A)

**Product model (13/08/2026):** on the desktop there is **one** connector capability — **Workproba Cloud** (`workproba.cloud`, catalog id `workproba_cloud`), listed **first** in the Capabilities hub. **Project management** (`projects` / `workproba.projet`) and org services from the control plane (`echo`, `ihora.shaped`, `ihora`, **Pennylane**, **GazFlow**, …) appear in a **collapsible** sub-capabilities zone under Cloud (compact cards). Guided mode hides technical stubs (`echo`, `ihora.shaped`).

**Per-space profile:** `{space}/.workproba/capabilities.json` stores `wanted` for local ids and `managed:{connectorId}`. `{space}/.workproba/space_policy.json` stores `approvalMode` (`security` / `trust`). UI: `SpaceSettingsDialog` / `SpaceCapabilitiesPanel` / `useSpacePolicy`. Sidecar: `GET` / `PUT /workspace/capabilities` and `GET` / `PUT /workspace/policy`. Agent turns freeze effective plugins + managed allowlist once (`TurnCapabilitiesSnapshot` in `capabilities_turn.py`).

Standard path for managed capabilities (MVP 20/07/2026 ; hub hierarchy 21/07 ; space profile + dedicated tools 22–23/07). Plugin `workproba.cloud` :

- **Desktop auth UX**: `CloudLoginModal` + `cloudDesktopAuth.ts` (`POST /devices/login` → User JWT → exchange `POST /devices/desktop-bearer` → DeviceBearer `wp_dev_*`); `EnrollCloudModal` / `EnrollCloudJoinForm` (`join_token` → DeviceBearer). First-run: `EngineOnboardingWizard`. Cloud web links: `cloudWebUrls.ts` (`VITE_CLOUD_WEB_URL`).
- **`CloudControlPlaneClient`** : join via `join_token`, or login bearer JWT exchanged to durable `wp_dev_*` (`ensure_durable_device_bearer` on status) ; catalogs, regards (`/plugins/cloud/enroll`, `/plugins/cloud/sync-regards`)
- **`RemoteCapabilityGateway`** : relay to org-allowed services (`echo`, `ihora.shaped` stub, `ihora` HTTP, **Pennylane**, **GazFlow**) via `POST /connectors/{id}/invoke` (payload only ; no client `subject_id` / `org_id`). Used by **SpecialistRun** and operative connector tools — the parent assistant does not call `managed_*` directly when delegating to an agent métier (`summon_specialist`). **`tools[]` contract** (cloud authoritative): each connector in `GET /connectors` may list tools with `name`, `action`, `description`, `effect`, `visibility`, `input_schema`, plus connector fields `enableByDefaultInProjects` and `requiresSecrets`. List response includes `catalogVersion`. The front catalog mirrors defaults for local capabilities (`workproba_cloud`, `projects`, `regards`, `web_navigation`) and managed ones (`managed:{connectorId}`). Sidecar `GET /plugins/cloud/connectors` caches id/name/tools for the agent. For each connector effective in the space, operative runs may register dedicated tools `managed_{connector_id}_{name}` (`.` → `_` in connector id). **`invoke_managed_connector`** remains the generic fallback inside SpecialistRun. Cloud re-validates `payload.action` and schema at invoke. Human Approval Gate (`external_send`) with managed confirmation layout + human summaries; `confirmation_preparing` before pre-resolution; **approve remaining** (`trust_key` turn-scoped); space **Confiance** uses `AutoApproveGate`. Unknown catalog actions trigger `ModelRetry` (inventory guard). Guided mode skips `visibility: advanced` tools. Product UI: managed capabilities under Workproba Cloud ; CloudPanel lists tool names and descriptions (not schemas). Ihora example: **17 tools** incl. `list_users`, `create_project_budget`, `update_project_budget` ; then `update_project_member` / `create_project` with numeric userIds (or email resolved server-side / pre-confirm). Pennylane: curated Company API v2 (customers, invoices, quotes). GazFlow: 13 tools NoVa/N-1/batch, `enableByDefaultInProjects: false`.
- **`ManagedAgentsPort`** for enterprise agents (code current: `ManagedRegardsPort`)
- **`ProjectSyncPort`** mount sync = technical NAS only, deprecated product path, **rejected when enrolled**
- Shared project SoT = cloud (list/publish/open/republish via API + S3, local = disposable cache)
- Direct poste→external connectors (mode C) = power-user, not promoted

See [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md). No direct project or personas namespace access.

## Experimental plugins

- **Browser**: see [browser.md](./browser.md) (opt-in, bundled Chromium, Capabilities hub)

## Local plugins

Tauri can copy and register a local plugin folder. **Runtime loading (Python tools + Vue components) is not implemented in V2.** Hidden in production builds unless `VITE_LOCAL_PLUGIN_INSTALL=true` (dev builds always allow install).

## See also

- [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md): capabilities UX plan
- [contrat-plugin.md](../../workproba-improba/roadmaps/contrat-plugin.md): contract + implementation matrix
- [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md): Improba Cloud (auth, connector presets, relay)
- [memory.md](./memory.md): scoped memory
- [architecture.md](./architecture.md): UI shell
- [services/ai/README.md](../services/ai/README.md): endpoint catalog
